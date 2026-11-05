/** @odoo-module */

import { PosPayment } from "@point_of_sale/app/models/pos_payment";
import { patch } from "@web/core/utils/patch";
import { GT, LT } from "@point_of_sale/app/utils/numbers";
import { roundPrecision } from "@web/core/utils/numbers";

// Live patch for Odoo 19 PosPayment.
//
// Keeps `foreign_amount` (the display amount in the *foreign* currency) in
// sync with `amount` (the amount in the POS main currency), using the
// conversion helpers exposed by pos.order (which respect the "which one is
// the main currency" business rule).
patch(PosPayment.prototype, {
    setup(vals) {
        super.setup(...arguments);
        this.foreign_amount = vals.foreign_amount || 0;
        this.foreign_rate = vals.foreign_rate || 0;
        this.tender_amount = vals.tender_amount || 0;
    },

    serializeForORM(opts = {}) {
        const data = super.serializeForORM(opts);
        data["foreign_amount"] = this.foreign_amount || 0;
        // `foreign_rate` is not set here: the order sync serializes its
        // payments without calling this method, so the rate is stamped on the
        // order's payment commands (PosOrder._setPaymentForeignRates).
        // Lo mismo con la moneda de cobro: en la sincronización llega
        // `tender_amount` (campo del registro) y el servidor pone la moneda del
        // método (pos.order._set_payment_tender_values).
        const currency = this.getTenderCurrency();
        data["tender_currency_id"] = currency ? currency.id : false;
        data["tender_amount"] = currency ? this.getTenderAmount() : 0;
        return data;
    },

    // ---- Moneda de cobro (tercera moneda, p. ej. EUR) ----
    //
    // Un método con `tender_currency_id` se cobra en esa moneda: el cajero
    // teclea euros y la línea vale en la caja su conversión con la tasa del
    // día (pos.config.tender_currency_rates, vía pos_order._getPosConversionRate).
    // `amount` sigue en la moneda de la caja (lo que el core suma, cobra y
    // contabiliza), `foreign_amount` en la alterna (derivado de `amount`, como
    // en todo método) y `tender_amount` es lo tecleado: lo que entra al cajón
    // en euros y al diario real en esa moneda.
    //
    // binaural_pos_multicurrency extiende getTenderCurrency (cobro en la moneda
    // de la compañía en una caja en otra moneda) y los ganchos _getTenderDue /
    // _getPartialTenderLocalAmount.

    // Un pago ya guardado conserva la moneda con la que se cobró
    // (pos.payment.tender_currency_id), aunque después cambie la del método:
    // al reimprimir un recibo viejo salen los euros que se cobraron. Una línea
    // nueva aún no la tiene y toma la del método.
    getTenderCurrency() {
        const order = this.pos_order_id;
        const currency = this.tender_currency_id || this.payment_method_id?.tender_currency_id;
        if (!order || !currency) {
            return null;
        }
        if (order._currencyId(currency) === order._currencyId(order._getMainCurrency())) {
            return null;
        }
        return order._resolveCurrencyRecord(currency);
    },

    getTenderAmount() {
        return this.tender_amount || 0;
    },

    // Multiplicadores { toTender: caja → cobro, toLocal: cobro → caja }. En un
    // reembolso, la tasa con la que se cobraron los pagos originales en esa
    // moneda (pos.order.get_refund_tender_rates, precargada por la pantalla de
    // pago): se devuelven los mismos euros. Si no, la tasa viva de la caja.
    _getTenderRates(currency = this.getTenderCurrency()) {
        const order = this.pos_order_id;
        const refundRate = Number(order?.getRefundTenderRate?.(currency)) || 0;
        if (refundRate > 0) {
            return { toTender: 1 / refundRate, toLocal: refundRate };
        }
        const main = order._getMainCurrency();
        return {
            toTender: order._getPosConversionRate(main, currency),
            toLocal: order._getPosConversionRate(currency, main),
        };
    },

    _recomputeTenderFromLocal() {
        const currency = this.getTenderCurrency();
        if (!currency) {
            this.tender_amount = 0;
            return;
        }
        this.tender_amount = this.pos_order_id._convertAtRate(
            this.amount || 0,
            this._getTenderRates(currency).toTender,
            currency
        );
    },

    // Restante de la orden en la moneda de la caja ANTES de esta línea (con el
    // signo del total): total menos los demás pagos hechos, sin vueltos.
    // l10n_ve_pos_igtf lo extiende con la deuda IGTF.
    _getLocalDueBefore() {
        const order = this.pos_order_id;
        const localTotal = Number(order.totalDue ?? 0) || 0;
        const paidOthers = Array.from(order.payment_ids || []).reduce((sum, line) => {
            if (line === this || !line.isDone() || line.is_change) {
                return sum;
            }
            return sum + (Number(line.getAmount()) || 0);
        }, 0);
        return localTotal - paidOthers;
    },

    // Lo adeudado en la moneda de cobro: el restante de la caja convertido
    // UNA vez y redondeado a esa moneda (lo que el cajero ve propuesto).
    _getTenderDue(currency, localDueBefore, rates) {
        return this.pos_order_id._convertAtRate(localDueBefore, rates.toTender, currency);
    },

    // Monto en la caja de un cobro parcial (no cubre lo adeudado): la
    // conversión de lo tecleado, con el signo del restante (un reembolso
    // tecleado sin "-" sigue siendo una salida).
    _getPartialTenderLocalAmount(currency, requested, tenderDue, localDueBefore, rates) {
        const signed = localDueBefore < 0 && requested > 0 ? -requested : requested;
        return this.pos_order_id._convertAtRate(
            signed,
            rates.toLocal,
            this.pos_order_id._getMainCurrency()
        );
    },

    setTenderAmount(amount) {
        // Mismo criterio que set_foreign_amount para la alterna: si lo tecleado
        // cubre lo adeudado (comparado en la moneda de cobro, con su redondeo),
        // el monto de la caja es EXACTAMENTE el restante más el excedente
        // convertido, para que el ruido cambiario no deje un céntimo pendiente
        // ni un vuelto fantasma. Si no lo cubre, la conversión de lo tecleado.
        const order = this.pos_order_id;
        const currency = this.getTenderCurrency();
        const requested = Number(amount) || 0;
        if (!order || !currency) {
            this.setAmount(requested);
            return;
        }
        const posCurrency = order._getMainCurrency();
        const rates = this._getTenderRates(currency);
        const localDueBefore = this._getLocalDueBefore();
        const tenderDue = this._getTenderDue(currency, localDueBefore, rates);

        const absRequested = Math.abs(requested);
        const absDue = Math.abs(tenderDue);
        const coversDue = !currency.isZero(tenderDue) && currency.comp(absRequested, absDue) !== LT;

        let localAmount;
        if (coversDue) {
            const overpayment = absRequested - absDue;
            const sign = localDueBefore < 0 ? -1 : 1;
            localAmount = currency.isPositive(overpayment)
                ? localDueBefore +
                  sign * order._convertAtRate(overpayment, rates.toLocal, posCurrency)
                : localDueBefore;
        } else {
            localAmount = this._getPartialTenderLocalAmount(
                currency, requested, tenderDue, localDueBefore, rates
            );
        }

        this._settingTenderAmount = true;
        try {
            this.setAmount(localAmount);
        } finally {
            this._settingTenderAmount = false;
        }
        // Mismo signo que `amount` y redondeado a la moneda de cobro.
        const sign = (localAmount || requested) < 0 ? -1 : 1;
        this.tender_amount = currency.round(sign * absRequested);
    },

    _recomputeForeignFromLocal() {
        // Called when the local `amount` is the source of truth (core setAmount).
        // Uses the centralized pos_order._convert (mirror of pos.config._convert).
        //
        // Runs for EVERY payment method, not just is_foreign_currency ones.
        // A payment tendered in local currency (Bs) still needs its USD
        // equivalent for dual-currency accounting — see
        // openspec/migration-lessons.md, "Pendientes por tratar
        // (2026-07-10)". Gating this on is_foreign_currency used to zero
        // foreign_amount for local-method payments, which silently zeroed
        // foreign_debit/foreign_credit on every downstream accounting line
        // (pos_session.py session close, pos_payment.py invoice payment
        // moves) even though the conversion itself has nothing to do with
        // which currency the cashier typed the amount in.
        const order = this.pos_order_id;
        if (!order || typeof order.localToForeign !== "function") {
            this.foreign_amount = 0;
            return;
        }
        // _convertOrderAmount uses the refund's original-sale rate when the
        // order has refund lines, and the live rate otherwise. This keeps a
        // refund paid in local currency (Bs) valued in USD at the SAME rate
        // as the refund total, instead of today's rate.
        this.foreign_amount = order._convertOrderAmount(this.amount || 0);
    },

    setAmount(value) {
        super.setAmount(value);
        this._recomputeForeignFromLocal();
        // Con el monto de la caja como fuente (core, botones +10, precarga),
        // lo cobrado en la moneda de cobro es su conversión. setTenderAmount
        // fija `tender_amount` con lo tecleado y lo salta.
        if (!this._settingTenderAmount) {
            this._recomputeTenderFromLocal();
        }
    },

    get_amount() {
        // Odoo 19 renamed to getAmount(); keep get_amount() as an alias
        // because our templates and helpers still use snake_case.
        return this.getAmount();
    },

    get_foreign_amount() {
        return this.foreign_amount || 0;
    },

    set_foreign_amount(amount) {
        // Foreign method: the user typed the foreign amount directly. We
        // need to compute the equivalent LOCAL amount so the core's
        // remainingDue = totalDue - amountPaid works.
        //
        // Business rule (Odoo native behavior for foreign payments): when
        // the foreign amount covers the foreign due of the order, we treat
        // the order as fully settled — the local `amount` is set to exactly
        // the LOCAL remaining due, not the mathematical `foreign / rate`.
        // Difference between them is FX-rounding noise that in real
        // accounting is absorbed by an FX gain/loss entry.
        //
        // If the foreign amount is a partial payment (< foreign due), fall
        // back to strict conversion.
        //
        // Combined payments (some lines in local, some in foreign) work
        // because the foreign due is always derived from the LOCAL remaining
        // due (totalDue - amountPaid across ALL payment lines, whatever their
        // currency), then converted once. That way lines paid in local
        // currency count correctly toward the foreign due.
        const order = this.pos_order_id;
        const requested = Number(amount) || 0;
        this.foreign_amount = requested;

        if (!order || typeof order.foreignToLocal !== "function") {
            this.amount = 0;
            return;
        }

        // Local remaining due BEFORE this payment line.
        // Uses core totalDue/amountPaid semantics but subtracts SELF so a
        // re-edit of the same line doesn't cascade.
        const localTotal = Number(order.totalDue ?? 0) || 0;
        const localPaidOthers = Array.from(order.payment_ids || []).reduce((sum, line) => {
            if (line === this) return sum;
            const done = typeof line.isDone === "function" ? line.isDone() : true;
            if (!done) return sum;
            const lineAmount = typeof line.getAmount === "function"
                ? line.getAmount()
                : (line.amount || 0);
            return sum + (Number(lineAmount) || 0);
        }, 0);
        const localDueBefore = localTotal - localPaidOthers;

        // Refund with a KNOWN original foreign rate (prefetched by the payment
        // screen from the original order's foreign tender): mirror the tender
        // exactly. Value the line as |foreign| * rate (direct), so refunding
        // $45 gives back the SAME Bs the original $45 payment recorded
        // (matches "ver pagos de origen" to the cent), instead of the
        // sale-oriented due-snapping below. Only snap to the exact local due
        // when the tender just covers it (within one foreign-rounding step),
        // to kill the sub-cent drift of the rounded foreign due on a full
        // refund. Refund lines are negative, so foreign_amount is negated too.
        const exactRate = typeof order.getRefundForeignRate === "function"
            ? order.getRefundForeignRate() : 0;
        if (exactRate > 0) {
            const sign = localTotal < 0 ? -1 : 1;
            const mag = Math.abs(requested);
            this.foreign_amount = sign * mag;
            // foreign→local at the exact original rate, via the shared engine
            // primitive (exactRate is already local-per-foreign).
            const directLocal = order.foreignToLocalAtRate(mag, exactRate);
            const absDue = Math.abs(localDueBefore);
            // "Covers the due" is decided in the currency the cashier typed:
            // the typed magnitude is at most one foreign step away from the
            // due the cashier sees (the exact-rate due rounded to the foreign
            // currency; main→foreign multiplier 1/exactRate). currency.comp
            // rounds both operands first, so float noise right at the step
            // (0.40000000000009 Bs for 1 cent at 40) no longer turns the
            // boundary into a mirror (task 83148, H20).
            const fc = order._resolveCurrencyRecord?.(order.get_foreign_currency?.())
                ?? order.get_foreign_currency?.();
            const fRounding = Number(fc?.rounding)
                || Number(order._getForeignCurrencyRecord?.()?.rounding) || 0.01;
            const dueForeign = order.localToForeignAtRate(absDue, 1 / exactRate, false);
            const hasComp = typeof fc?.comp === "function";
            const dueShown = hasComp
                ? fc.round(dueForeign)
                : roundPrecision(dueForeign, fRounding);
            const distance = Math.abs(mag - dueShown); // magnitudes, no sign
            // Typed amounts come in foreign steps, so the distance is a whole
            // number of steps plus noise: half a step separates 1 from 2.
            const coversDue = hasComp
                ? fc.comp(distance, fRounding) !== GT
                : distance < fRounding * 1.5;
            this.amount = coversDue
                ? localDueBefore // full/exact refund: snap to due, no drift
                : sign * directLocal; // overpay/partial: mirror the tender
            return;
        }

        // A refund payment carries the refund's sign even if the cashier
        // typed a positive amount (task 83148, H1). Sales keep what was typed.
        const sign = localTotal < 0 ? -1 : 1;
        const signedRequested = sign < 0 && requested > 0 ? -requested : requested;
        this.foreign_amount = signedRequested;

        // Convert local due to foreign ONCE (same rounding as
        // get_foreign_total_with_tax → foreign_currency.round).
        //
        // _convertOrderAmount (not the raw localToForeign) so a REFUND uses
        // the frozen original-sale rate, not today's live rate: otherwise the
        // foreign due shown/typed here diverges from the foreign amount the
        // original payment actually had (visible via "ver pagos de origen").
        const foreignDueBefore = order._convertOrderAmount(localDueBefore);

        // Resolve the real ResCurrency record (AbstractNumbers) when
        // possible; get_foreign_currency may return a bare id.
        const fc = order._resolveCurrencyRecord?.(order.get_foreign_currency?.())
            ?? order.get_foreign_currency?.();
        const hasComp = Boolean(fc && typeof fc.comp === "function");

        // "Covers the due" means |requested| >= |due|. Works for both
        // positive (sales) and negative (refunds) amounts, and for mixed
        // signs (comparison is on magnitudes).
        const absRequested = requested < 0 ? -requested : requested;
        const absDue = foreignDueBefore < 0 ? -foreignDueBefore : foreignDueBefore;

        // currency.comp() rounds both operands to the foreign currency
        // precision before comparing, so the half-rounding tolerance is
        // built in. isZero() also treats sub-rounding residual due (fx
        // noise) as "nothing due". Manual fallback for unresolved currency.
        const coversDue = hasComp
            ? !fc.isZero(foreignDueBefore) && fc.comp(absRequested, absDue) !== LT
            : foreignDueBefore !== 0
                && absRequested + (Number(fc?.rounding) || 0.01) / 2 >= absDue;

        if (coversDue) {
            // Payment covers the local due exactly, plus any overpay.
            // isPositive() discards float-noise "overpay" below the
            // currency precision instead of converting it. The overpay is a
            // magnitude: it takes the sign of the due (negative on a refund).
            const overpaymentForeign = absRequested - absDue;
            const hasOverpay = hasComp
                ? fc.isPositive(overpaymentForeign)
                : overpaymentForeign > 0;
            const overpaymentLocal = hasOverpay
                ? sign * order._convertForeignOrderAmount(overpaymentForeign)
                : 0;
            this.amount = localDueBefore + overpaymentLocal;
            return;
        }

        // Partial payment: strict mathematical conversion. Refund-aware so a
        // partial refund's local (main-currency) amount is proportional to
        // the original sale's rate, not today's rate.
        this.amount = order._convertForeignOrderAmount(signedRequested);
    },
});
