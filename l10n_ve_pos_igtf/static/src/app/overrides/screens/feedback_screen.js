import { FeedbackScreen } from "@point_of_sale/app/screens/feedback_screen/feedback_screen";
import { patch } from "@web/core/utils/patch";

// Pantalla "Pago exitoso": el core muestra el total de la FACTURA
// (order.totalDue) en la moneda del primer pago, y l10n_ve_pos le añade el
// total en moneda alterna. Ninguno contempla el IGTF, así que la pantalla que
// confirma el cobro mostraba menos de lo que el cliente acaba de pagar
// (12.806,40 Bs / $17,37 en vez de 13.027,57 Bs / $17,67).
//
// Aquí la orden ya está validada, de modo que el IGTF a mostrar es el REAL
// cobrado (order.igtf_amount), no el 3% fijo de la factura completa que usa
// el panel de estado de pago. Sin IGTF todo se comporta como antes.
patch(FeedbackScreen.prototype, {
  get igtfAmount() {
    return Number(this.currentOrder?.get_igtf_amount?.()) || 0;
  },
  get igtfAmountLabel() {
    return this.pos.formatCurrency(this.igtfAmount);
  },
  get foreignIgtfAmountLabel() {
    return this.pos.formatForeignCurrency(this.currentOrder.get_foreign_igtf_amount());
  },
  get paymentAmountWithIgtf() {
    const order = this.currentOrder;
    if (!this.igtfAmount) {
      return order.paymentAmountInCurrency;
    }
    return order.formatAmountInCurrency(
      order.totalDue + this.igtfAmount,
      order.orderCurrency
    );
  },
  get foreignAmountWithIgtf() {
    const order = this.currentOrder;
    const amount = this.igtfAmount
      ? order.get_foreign_total_paid_with_igtf()
      : order.get_foreign_total_with_tax();
    return this.pos.formatForeignCurrency(amount);
  },
});
