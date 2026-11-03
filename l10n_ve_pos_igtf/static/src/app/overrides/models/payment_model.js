/** @odoo-module */

import { PosPayment } from "@point_of_sale/app/models/pos_payment";
import { patch } from "@web/core/utils/patch";
// _getLocalDueBefore extiende el de l10n_ve_pos (moneda de cobro) con super:
// este parche debe aplicarse después. En el bundle lo asegura el orden de
// dependencias; en Hoot, el orden de importación.
import "@l10n_ve_pos/overrides/models/payment_model";

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
    // El clamp "cubre lo que se debe" de l10n_ve_pos no conoce el recargo
    // IGTF: calcula el due desde totalDue (sin deuda IGTF) y convertir el
    // excedente foráneo de vuelta a local reintroduce ruido de redondeo
    // (p.ej. 351 vs 348 Bs al pagar la deuda IGTF). Cuando la orden tiene
    // contexto IGTF (método apply_igtf o deuda IGTF acumulada, con cualquier
    // método), el due correcto es el RESTANTE actual: base de factura
    // pendiente + deuda IGTF, SIN el IGTF que esta línea generará (ese nace
    // después, en update_igtf — diseño 2026-07-09). Si el monto tecleado lo
    // cubre, fijamos el local EXACTO sin ida y vuelta de conversión.
    const order = this.pos_order_id;
    const method = this.payment_method_id;
    const hasIgtfContext =
      Boolean(method?.apply_igtf) ||
      (typeof order?._igtfRoundLocal === "function" &&
        order._igtfRoundLocal(order.igtf_amount || 0) !== 0);
    if (
      order?.to_invoice &&
      hasIgtfContext &&
      typeof order._igtfBaseState === "function" &&
      typeof order.localToForeign === "function"
    ) {
      const requested = Number(amount) || 0;
      const { sign, remainingBase, unpaidIgtf } = order._igtfBaseState(this);
      const dueLocal = order._igtfRoundLocal(sign * (remainingBase + unpaidIgtf));
      const dueForeign = order.localToForeign(dueLocal);
      // Espacio normalizado por signo (montos de pago positivos), sin
      // Math.abs; comparación con tolerancia de la moneda foránea vía
      // roundForeignMoney (equivalente JS de float_compare).
      const requestedN = sign * requested;
      const dueN = sign * dueForeign;
      const overpayForeign = order.roundForeignMoney(requestedN - dueN);
      if (dueN > 0 && requestedN > 0 && overpayForeign >= 0) {
        this.foreign_amount = order.roundForeignMoney(requested);
        const overpayLocal =
          overpayForeign > 0 && typeof order.foreignToLocal === "function"
            ? order.foreignToLocal(overpayForeign)
            : 0;
        this.amount = order._igtfRoundLocal(dueLocal + sign * overpayLocal);
        return;
      }
    }
    return super.set_foreign_amount(...arguments);
  },
  // La orden se factura y tiene contexto IGTF: el método de esta línea genera
  // IGTF o ya hay deuda IGTF acumulada (con cualquier método). Misma condición
  // que set_foreign_amount.
  _hasIgtfContext() {
    const order = this.pos_order_id;
    const method = this.payment_method_id;
    const hasIgtfContext =
      Boolean(method?.apply_igtf) ||
      (typeof order?._igtfRoundLocal === "function" &&
        order._igtfRoundLocal(order.igtf_amount || 0) !== 0);
    return Boolean(
      order?.to_invoice && hasIgtfContext && typeof order._igtfBaseState === "function"
    );
  },
  // Restante antes de esta línea para la moneda de cobro (EUR...,
  // l10n_ve_pos setTenderAmount): en contexto IGTF, el mismo que usa el ajuste
  // de set_foreign_amount, base de factura pendiente + deuda IGTF, SIN el IGTF
  // que esta línea generará. Si lo tecleado lo cubre, la línea vale ese monto
  // exacto (más el excedente), sin ida y vuelta de conversión.
  _getLocalDueBefore() {
    if (this._hasIgtfContext()) {
      const order = this.pos_order_id;
      const { sign, remainingBase, unpaidIgtf } = order._igtfBaseState(this);
      return order._igtfRoundLocal(sign * (remainingBase + unpaidIgtf));
    }
    return super._getLocalDueBefore(...arguments);
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
