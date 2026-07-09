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
  get_foreign_total_without_igtf() {
    const base = Number(this.totalDue ?? 0) || 0;
    return typeof this.localToForeign === "function" ? this.localToForeign(base) : 0;
  },
  get_total_with_tax() {
    // update_igtf garantiza igtf_amount = 0 cuando no hay líneas apply_igtf,
    // así que basta sumar y redondear con la moneda principal.
    const res = Number(this.totalDue ?? 0) || 0;
    return this._igtfRoundLocal(res + (this.igtf_amount || 0));
  },
  get_foreign_total_with_tax() {
    // Regla de redondeo l10n_ve_pos: cada total foráneo es UNA conversión
    // de su contraparte local, nunca la suma de conversiones redondeadas
    // (round(a) + round(b) != round(a + b) → diferencias de 0,01 entre el
    // total, la línea de pago y el restante foráneo).
    return this._igtfToForeign(this.get_total_with_tax());
  },

  get_igtf_amount() {
    return this.igtf_amount;
  },

  get_foreign_igtf_amount() {
    return this.foreign_igtf_amount;
  },

  // --- O19: remainingDue must include IGTF surcharge ---
  //
  // Core O19's remainingDue = totalDue - amountPaid. It doesn't know about
  // IGTF. So the "Remaining" shown by the core PaymentScreenStatus (which
  // reads this.order.remainingDue) is wrong when IGTF applies.
  //
  // We override the getter to add this.igtf_amount on top of the core value,
  // but only when the IGTF debt hasn't been fully paid yet (amountPaid <
  // totalDue + igtf_amount). This prevents the infinite-IGTF-debt scenario:
  // when the user pays the IGTF too, remainingDue correctly goes to 0.
  //
  // The anti-infinite-3%-loop lives in _igtfBaseState: IGTF is 3% of the
  // BASE portion each line covers, so the IGTF debt included in a closing
  // line never generates more IGTF.
  get remainingDue() {
    const base = _coreRemainingDue ? _coreRemainingDue.call(this) : 0;
    const igtf = this.igtf_amount || 0;
    const sign = this.totalDue < 0 ? -1 : 1;
    // Espacio normalizado por signo: en reembolsos base e igtf son negativos.
    const paidVsTotal = this._igtfRoundLocal(
      sign * (this.amountPaid - (this.totalDue + igtf))
    );
    if (sign * base <= 0 && paidVsTotal >= 0) {
      return 0;
    }
    return this._igtfRoundLocal(base + igtf);
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
  addPaymentline(payment_method) {
    const sign = this.get_total_without_igtf() < 0 ? -1 : 1;
    const is_change = sign * this.get_due() < 0;
    // Solo queda deuda IGTF por cobrar (la base está cubierta): la línea no
    // debe generar IGTF nuevo, el fill normal del core (remainingDue) basta.
    const only_igtf_debt_left =
      this._igtfRoundLocal(sign * (this.get_due() - this.get_igtf_amount())) <= 0;

    if (
      !this.to_invoice ||
      !payment_method.apply_igtf ||
      only_igtf_debt_left ||
      is_change
    ) {
      // Non-IGTF case: delegate to O19 original addPaymentline
      let res = super.addPaymentline(...arguments);
      this.update_igtf();
      return res;
    }
    // IGTF case: create payment prefilled with the closing amount
    let newPaymentline = this.add_paymentline_without_igtf(...arguments);
    this.update_igtf();
    if (!newPaymentline) {
      return { status: false, data: "Electronic payment in progress" };
    }
    return { status: true, data: newPaymentline };
  },

  add_paymentline_without_igtf(payment_method) {
    this.assert_editable();
    if (this.electronic_payment_in_progress()) {
      return false;
    }
    const newPaymentline = this.models["pos.payment"].create({
      pos_order_id: this,
      payment_method_id: payment_method,
      amount: 0,
    });
    this.select_paymentline(newPaymentline);
    if (this.config.cash_rounding) {
      newPaymentline.setAmount(0);
    }

    // Monto de cierre en UNA línea: base restante + deuda IGTF pendiente
    // + IGTF que genera la nueva base. La porción IGTF no genera IGTF
    // (ver _igtfBaseState). Todo en moneda local; para métodos foráneos
    // setAmount recalcula foreign_amount con una sola conversión.
    const { sign, remainingBase, unpaidIgtf } =
      this._igtfBaseState(newPaymentline);
    const totalPayment = this._igtfRoundLocal(
      sign * (remainingBase + unpaidIgtf + this.compute_igtf_amount(remainingBase))
    );
    newPaymentline.setAmount(totalPayment);

    if (payment_method.payment_terminal) {
      newPaymentline.setPaymentStatus("pending");
    }
    return newPaymentline;
  },
});
