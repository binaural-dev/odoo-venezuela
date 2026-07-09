/** @odoo-module */

import { PaymentScreenStatus } from "@point_of_sale/app/screens/payment_screen/payment_status/payment_status";
import { patch } from "@web/core/utils/patch";

// -----------------------------------------------------------------------------
// Foreign totals in the payment screen status panel.
//
// This override does NOT compute anything itself. All foreign math is
// delegated to the pos.order helpers (get_foreign_total_with_tax,
// get_foreign_due, get_foreign_change), which use the centralized
// _convert/roundForeignMoney and respect the rounding rule
// (see engram architecture/l10n-ve-pos/rounding-rule).
// -----------------------------------------------------------------------------

patch(PaymentScreenStatus.prototype, {
  _num(value, fallback = 0) {
    const n = Number(value);
    return Number.isFinite(n) ? n : fallback;
  },

  _callOrder(methodName, fallback = 0) {
    const order = this.props?.order;
    if (!order || typeof order[methodName] !== "function") {
      return fallback;
    }
    return this._num(order[methodName](), fallback);
  },

  _getForeignTotalDueAmount() {
    // Leer payment_ids para que Odoo/OWL trackee cambios reactivos
    const _paymentWatch = this.props?.order?.payment_ids;
    // get_foreign_total_with_tax es la única fuente del total foráneo.
    // Si l10n_ve_pos_igtf está instalado, su parche ya incluye el IGTF
    // (una sola conversión del total local); NO sumar el IGTF aquí de
    // nuevo — eso duplicaba el recargo en pantalla ($18,23 vs $17,70).
    return this._callOrder("get_foreign_total_with_tax", 0);
  },

  _getForeignRemainingAmount() {
    const _paymentWatch = this.props?.order?.payment_ids;
    return Math.max(0, this._callOrder("get_foreign_due", 0));
  },

  _getForeignChangeAmount() {
    const _paymentWatch = this.props?.order?.payment_ids;
    return Math.max(0, this._callOrder("get_foreign_change", 0));
  },

  get foreignTotalDueText() {
    return this.env.utils.formatForeignCurrency(this._getForeignTotalDueAmount());
  },

  get foreignRemainingText() {
    return this.env.utils.formatForeignCurrency(this._getForeignRemainingAmount());
  },

  get foreignChangeText() {
    return this.env.utils.formatForeignCurrency(this._getForeignChangeAmount());
  },

  get currentOrder() {
    return this.props.order;
  },

  // Odoo 19 native bug: isRemaining usa `remainingDue > 0` para reembolsos,
  // que es falso cuando el reembolso quedó cubierto (remainingDue=0).
  // Para un reembolso con pago completo, debe mostrar "Cambio" no
  // "Restantes" con valor 0.
  get isRemaining() {
    const order = this.props?.order;
    if (!order) return super.isRemaining;
    const isNegative = order.totalDue < 0;
    const remainingDue = order.remainingDue;
    const amountPaid = order.amountPaid;
    if (isNegative) {
      // Refund: si paid <= total (en valor absoluto), hay restante.
      // Si paid > total, es cambio (aunque remainingDue sea 0 por redondeo).
      return amountPaid > order.totalDue; // paid es negativo, total es negativo
    }
    // Venta: comportamiento nativo.
    return super.isRemaining;
  },
});
