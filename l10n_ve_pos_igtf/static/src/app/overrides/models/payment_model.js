/** @odoo-module */

import { PosPayment } from "@point_of_sale/app/models/pos_payment";
import { patch } from "@web/core/utils/patch";

patch(PosPayment.prototype, {
  setup(_defaultObj, options) {
    super.setup(...arguments);
    this.igtf_amount = this.igtf_amount || 0
    this.foreign_igtf_amount = this.foreign_igtf_amount || 0
  },
  set_include_igtf(value) {
    this.include_igtf = value
  },
  set_igtf_amount(amount) {
    this.igtf_amount = amount
  },
  set_foreign_igtf_amount(amount) {
    this.foreign_igtf_amount = amount
  },
  set_foreign_amount(amount) {
    // Para métodos con apply_igtf, el clamp "cubre lo que se debe" de
    // l10n_ve_pos no conoce el recargo IGTF: convertir el excedente foráneo
    // de vuelta a local reintroduce ruido de redondeo (p.ej. 341 vs 348 Bs).
    // Si el monto foráneo tecleado cubre el monto de cierre (base restante +
    // deuda IGTF + IGTF de la nueva base), fijamos el monto local EXACTO
    // calculado en moneda principal, sin ida y vuelta de conversión.
    const order = this.pos_order_id;
    const method = this.payment_method_id;
    if (
      order?.to_invoice &&
      method?.apply_igtf &&
      typeof order._igtfBaseState === "function" &&
      typeof order.localToForeign === "function"
    ) {
      const requested = Number(amount) || 0;
      const { sign, remainingBase, unpaidIgtf } = order._igtfBaseState(this);
      const closingLocal = order._igtfRoundLocal(
        sign * (remainingBase + unpaidIgtf + order.compute_igtf_amount(remainingBase))
      );
      const closingForeign = order.localToForeign(closingLocal);
      // Espacio normalizado por signo (montos de pago positivos), sin
      // Math.abs; comparación con tolerancia de la moneda foránea vía
      // roundForeignMoney (equivalente JS de float_compare).
      const requestedN = sign * requested;
      const closingN = sign * closingForeign;
      const overpayForeign = order.roundForeignMoney(requestedN - closingN);
      if (closingN > 0 && requestedN > 0 && overpayForeign >= 0) {
        this.foreign_amount = order.roundForeignMoney(requested);
        const overpayLocal =
          overpayForeign > 0 && typeof order.foreignToLocal === "function"
            ? order.foreignToLocal(overpayForeign)
            : 0;
        this.amount = order._igtfRoundLocal(closingLocal + sign * overpayLocal);
        return;
      }
    }
    return super.set_foreign_amount(...arguments);
  },
  init_from_JSON(json) {
    super.init_from_JSON(...arguments);
    this.include_igtf = json.include_igtf || false;
    this.igtf_amount = json.igtf_amount || 0;
    this.foreign_igtf_amount = json.foreign_igtf_amount || 0;
  },
  export_as_JSON() {
    let res = super.export_as_JSON();
    res["include_igtf"] = this.include_igtf;
    res["igtf_amount"] = this.igtf_amount;
    res["foreign_igtf_amount"] = this.foreign_igtf_amount;
    return res
  },
});
