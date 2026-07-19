/** @odoo-module */

import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { PosPayment } from "@point_of_sale/app/models/pos_payment";
import { PosOrderAccounting } from "@point_of_sale/app/models/accounting/pos_order_accounting";
import { patch } from "@web/core/utils/patch";
import { floatIsZero } from "@web/core/utils/numbers";

// Save reference to core remainingDue getter so we can add IGTF on top
const _coreRemainingDue = Object.getOwnPropertyDescriptor(
    PosOrderAccounting.prototype, 'remainingDue'
)?.get;

// New orders are now associated with the current table, if any.
patch(PosOrder.prototype, {
  setup(_defaultObj, options) {
    super.setup(...arguments);
    this.igtf_amount = 0;
    this.foreign_igtf_amount = 0;
    this.bi_igtf = 0;
    this.foreign_bi_igtf = 0;
    this.update_igtf();
  },
  init_from_JSON(json) {
    super.init_from_JSON(...arguments);
    this.igtf_amount = json.igtf_amount;
    this.bi_igtf = json.bi_igtf;
    this.foreign_igtf_amount = json.foreign_igtf_amount;
    this.foreign_bi_igtf = json.foreign_bi_igtf;
  },
  export_as_JSON() {
    let json = super.export_as_JSON();
    json["igtf_amount"] = this.igtf_amount;
    json["bi_igtf"] = this.bi_igtf;
    json["foreign_igtf_amount"] = this.foreign_igtf_amount;
    json["foreign_bi_igtf"] = this.foreign_bi_igtf;
    return json;
  },
  // Único punto de entrega de los campos IGTF al backend.
  //
  // Los campos IGTF NO están en `_load_pos_data_fields` a propósito: eso los
  // haría campos reactivos, y update_igtf() los reescribe constantemente (hasta
  // desde setup()), marcando los registros `_dirty` y colgando el POS en un
  // bucle de render/sync. Se quedan como props JS planas y se inyectan aquí,
  // que solo corre al sincronizar la orden.
  //
  // Los pagos hijos se serializan por recursión directa (`deepSerialization`)
  // saltándose `PosPayment.serializeForORM`, así que hay que inyectarlos en los
  // comandos de `payment_ids` ([0, 0, vals] / [1, id, vals]), emparejando por uuid.
  serializeForORM(opts = {}) {
    const data = super.serializeForORM(opts);
    data["igtf_amount"] = this.igtf_amount || 0;
    data["bi_igtf"] = this.bi_igtf || 0;

    const paymentsByUuid = new Map(
      this.get_paymentlines().map((payment) => [payment.uuid, payment])
    );
    for (const command of data["payment_ids"] || []) {
      const vals = Array.isArray(command) && command.length === 3 ? command[2] : null;
      const payment = vals && paymentsByUuid.get(vals.uuid);
      if (!payment) {
        continue;
      }
      vals["include_igtf"] = Boolean(payment.include_igtf);
      vals["igtf_amount"] = payment.igtf_amount || 0;
      vals["foreign_igtf_amount"] = payment.foreign_igtf_amount || 0;
    }
    return data;
  },
  // Convierte un monto local a foráneo. El IGTF SIEMPRE se calcula sobre la
  // moneda principal de la DB (line.amount, aquí Bs); el lado foráneo es solo
  // display y se deriva con UNA conversión, nunca con un cálculo paralelo en
  // foráneo (eso producía drift de redondeo: 341 vs 348).
  _igtfToForeign(amount) {
    return typeof this.localToForeign === "function"
      ? this.localToForeign(amount)
      : 0;
  },
  // Redondeo monetario local canónico (regla l10n_ve_pos): delega en
  // roundLocalMoney (res.currency.round de la moneda principal).
  _igtfRoundLocal(amount) {
    if (typeof this.roundLocalMoney === "function") {
      return this.roundLocalMoney(amount);
    }
    return this.currency.round(amount);
  },
  // Recorre las líneas de pago en orden y rastrea, en moneda principal, qué
  // porción de cada línea cubre BASE de la factura y qué porción paga deuda
  // IGTF ya generada. Reglas de negocio:
  //   - IGTF = 3% solo de la base cubierta (nunca mayor a 3% del total de la
  //     factura, aunque el cliente pague de más).
  //   - La porción de un pago que salda deuda IGTF NO genera IGTF, aunque el
  //     método tenga apply_igtf.
  //   - Los pagos sin apply_igtf también consumen base (no generan IGTF) y su
  //     excedente puede saldar deuda IGTF.
  // `excludeLine` permite calcular el estado "antes" de una línea concreta
  // (para autocompletar su monto de cierre).
  _igtfBaseState(excludeLine = null) {
    const total = this.get_total_without_igtf();
    // Trabajamos en espacio normalizado por signo (montos de pago positivos)
    // para no depender de Math.abs: amt = sign * amount.
    const sign = total < 0 ? -1 : 1;
    let remainingBase = this._igtfRoundLocal(sign * total);
    let unpaidIgtf = 0;
    const lines = [];
    for (const payment of this.get_paymentlines()) {
      if (excludeLine && payment === excludeLine) {
        continue;
      }
      const amt = this._igtfRoundLocal(sign * (payment.amount || 0));
      const isIgtf = Boolean(payment.payment_method_id?.apply_igtf);
      const isChange = amt < 0;
      if (isChange || floatIsZero(amt, this.currency.decimal_places)) {
        lines.push({ payment, base: 0, newIgtf: 0, isChange, isIgtf });
        continue;
      }
      const base = amt < remainingBase ? amt : remainingBase;
      remainingBase = this._igtfRoundLocal(remainingBase - base);
      let newIgtf = 0;
      if (isIgtf) {
        newIgtf = this.compute_igtf_amount(base);
        unpaidIgtf = this._igtfRoundLocal(unpaidIgtf + newIgtf);
      }
      const excess = this._igtfRoundLocal(amt - base);
      if (excess > 0) {
        unpaidIgtf = excess < unpaidIgtf
          ? this._igtfRoundLocal(unpaidIgtf - excess)
          : 0;
      }
      lines.push({ payment, base, newIgtf, isChange, isIgtf });
    }
    return { sign, remainingBase, unpaidIgtf, lines };
  },
  update_igtf() {
    const paymentlines = this.get_paymentlines();

    this.igtf_amount = 0;
    this.foreign_igtf_amount = 0;
    this.bi_igtf = 0;
    this.foreign_bi_igtf = 0;

    paymentlines.forEach((payment) => {
      payment.set_include_igtf(false);
      payment.set_igtf_amount(0);
      payment.set_foreign_igtf_amount(0);
    });

    if (!this.to_invoice) {
      return this.igtf_amount;
    }

    const { sign, lines } = this._igtfBaseState();
    let totalIgtf = 0;
    let totalBase = 0;

    for (const { payment, base, newIgtf, isChange, isIgtf } of lines) {
      if (!isIgtf || isChange) {
        continue;
      }
      payment.set_include_igtf(true);
      payment.set_igtf_amount(sign * newIgtf);
      payment.set_foreign_igtf_amount(this._igtfToForeign(sign * newIgtf));
      totalIgtf += newIgtf;
      totalBase += base;
    }

    this.igtf_amount = this._igtfRoundLocal(sign * totalIgtf);
    this.foreign_igtf_amount = this._igtfToForeign(this.igtf_amount);
    this.bi_igtf = this._igtfRoundLocal(sign * totalBase);
    this.foreign_bi_igtf = this._igtfToForeign(this.bi_igtf);
    return this.igtf_amount;
  },
  compute_igtf_amount(amount) {
    return this._igtfRoundLocal(amount * (this.config.igtf_percentage / 100));
  },

  get_bi_igtf() {
    return this.bi_igtf;
  },

  get_total_without_igtf() {
    return Number(this.totalDue ?? 0) || 0;
  },

  get_igtf_amount() {
    return this.igtf_amount;
  },

  // Total de factura completa + 3% de esa MISMA factura completa. Fijo:
  // NO usa this.igtf_amount (ese es el recargo parcial que update_igtf()
  // acumula según la base ya cubierta por líneas de pago con apply_igtf, y
  // varía según lo tecleado en cada línea). Este getter es solo para el
  // renglón "TOTAL a Pagar con IGTF" del panel de estado de pago
  // (payment_status.xml), que debe mostrar siempre el mismo total sin
  // importar cuánto se haya pagado aún. No reemplaza get_total_with_tax()/
  // get_foreign_total_with_tax(), que deben seguir siendo la conversión pura
  // de factura para el resto de consumidores (ver migration-lessons.md,
  // "Resuelto 2026-07-14").
  get_total_with_igtf() {
    const total = this.get_total_without_igtf();
    return this._igtfRoundLocal(total + this.compute_igtf_amount(total));
  },

  get_foreign_igtf_amount() {
    return this.foreign_igtf_amount;
  },

  // --- O19: remainingDue must include IGTF surcharge ---
  //
  // Core O19's remainingDue = totalDue - amountPaid, CLAMPADO a 0 en cuanto
  // amountPaid >= totalDue. No sirve como base para componer: cuando una
  // línea absorbe deuda IGTF, amountPaid excede totalDue y el clamp pierde
  // ese exceso — sumarle igtf_amount completo devolvía la deuda IGTF TOTAL
  // (426,60) en vez de la pendiente (21,64) en el repro de la factura
  // 14.220: Zelle 13.498,61 (IGTF 404,96) + Zelle 1.126,35 (absorbe los
  // 404,96 y su base genera 21,64).
  //
  // Fórmula directa: (totalDue + igtf_amount) - amountPaid, que descuenta
  // TODO lo pagado (deuda IGTF saldada incluida). Sin IGTF delegamos en el
  // core intacto.
  //
  // The anti-infinite-3%-loop lives in _igtfBaseState: IGTF is 3% of the
  // BASE portion each line covers, so a line that pays IGTF debt never
  // generates more IGTF.
  //
  // Este getter es también la PRECARGA de toda línea nueva: el core
  // (getDefaultAmountDueToPayIn) lo lee, así que una línea nueva toma la
  // deuda de factura + la deuda IGTF acumulada, nunca su propio IGTF futuro.
  get remainingDue() {
    const igtf = this._igtfRoundLocal(this.igtf_amount || 0);
    if (igtf === 0) {
      return _coreRemainingDue ? _coreRemainingDue.call(this) : 0;
    }
    const sign = this.totalDue < 0 ? -1 : 1;
    const remaining = this._igtfRoundLocal(this.totalDue + igtf - this.amountPaid);
    if (sign * remaining <= 0) {
      return 0;
    }
    // Tolerancia de cash rounding, espejo del core (orderIsRounded +
    // asymmetricRound sobre el restante normalizado).
    if (
      this.orderIsRounded &&
      this.config.rounding_method?.asymmetricRound(sign * remaining) == 0
    ) {
      return 0;
    }
    return remaining;
  },

  // --- O19: change must respect the IGTF-inclusive effective total ---
  //
  // CONVENCIÓN DE SIGNO DEL CORE (pos_order_accounting.js::change): el vuelto
  // tiene el signo OPUESTO al total de la orden — negativo en ventas, positivo
  // en reembolsos. `setOrderPrices` lo manda como `amount_return`, y el backend
  // crea con él una línea de pago `is_change` que se SUMA a amount_paid
  // (pos_order.py::_process_payment_lines). Devolver el vuelto en positivo en
  // una venta inflaría amount_paid y dispararía "Order is not fully paid".
  //
  // Reescribimos el cálculo del core sustituyendo priceIncl por priceIncl +
  // igtf_amount (total efectivo que el cliente debe cubrir). Al desarrollar el
  // `isNegative ? -round(total) : round(total)` del core, ambas ramas colapsan
  // en la misma expresión, así que no hacen falta Math.abs ni ramas por signo.
  get change() {
    const igtf = this.igtf_amount || 0;
    const sign = this.totalDue < 0 ? -1 : 1;
    const remaining = this.totalDue + igtf - this.amountPaid;

    // Lo pagado no cubre el total efectivo → no hay vuelto.
    if (sign * remaining >= 0) {
      return 0;
    }

    const roundingSanatizer = this.orderIsRounded ? this.appliedRounding : 0;
    const amount = this._igtfRoundLocal(
      this.priceIncl + igtf - this.amountPaid + roundingSanatizer
    );
    return this.shouldRoundChange
      ? this.config.rounding_method.asymmetricRound(amount)
      : amount;
  },

  // --- Compat wrappers (O17 → O19) ---
  get_paymentlines() {
    return this.payment_ids ? Array.from(this.payment_ids) : [];
  },
  get_due() {
    return Number(this.remainingDue ?? 0) || 0;
  },
  get_rounding_applied() {
    // O19: renamed to roundingApplied getter in accounting mixin.
    return Number(this.roundingApplied ?? (typeof this.get_rounding_applied === "function" ? 0 : 0)) || 0;
  },
  get_foreign_rounding_applied() {
    // O19: no existe en core ni en l10n_ve_pos (método comentado).
    // El cash rounding en moneda extranjera no fue migrado.
    return 0;
  },
  add_paymentline(payment_method) {
    return this.addPaymentline(payment_method);
  },
  select_paymentline(line) {
    this.selectPaymentline(line);
  },
  assert_editable() {
    if (typeof this.assertEditable === "function") {
      this.assertEditable();
    }
  },
  electronic_payment_in_progress() {
    if (typeof this.electronicPaymentInProgress === "function") {
      return this.electronicPaymentInProgress();
    }
    return false;
  },
  get_selected_paymentline() {
    return (this.payment_ids || []).find(
      (line) => line.uuid === this.uiState?.selected_paymentline_uuid
    ) ?? null;
  },
  // La precarga es SIEMPRE la del core: remainingDue (deuda de factura +
  // deuda IGTF ya acumulada), sin importar el método. El IGTF que genere la
  // base cubierta por esta línea NO se incluye en su monto: nace después, en
  // update_igtf(), como nuevo restante que se paga en otra línea (decisión de
  // diseño 2026-07-09: separar la generación del IGTF de la línea de pago;
  // pagar una factura completa con un método apply_igtf son SIEMPRE dos
  // líneas). No restaurar el "cierre en una línea".
  addPaymentline(payment_method) {
    const res = super.addPaymentline(...arguments);
    this.update_igtf();
    return res;
  },
});
