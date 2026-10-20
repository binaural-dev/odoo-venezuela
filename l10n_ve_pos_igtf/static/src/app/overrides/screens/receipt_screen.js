/** @odoo-module */

import { ReceiptScreen } from "@point_of_sale/app/screens/receipt_screen/receipt_screen";
import { patch } from "@web/core/utils/patch";

// Pantalla "Pago exitoso": el core muestra el total de la FACTURA
// (order.priceIncl), y l10n_ve_pos le añade al lado el mismo total convertido
// a moneda foránea. Ninguno de los dos contempla el IGTF, así que la pantalla
// que confirma el cobro mostraba menos de lo que el cliente acaba de pagar
// (12.806,40 Bs / $17,37 en vez de 13.027,57 Bs / $17,67).
//
// Aquí la orden ya está validada, de modo que el IGTF a mostrar es el REAL
// cobrado (order.igtf_amount, vía get_total_paid_with_igtf()), no el 3% fijo
// de la factura completa que usa el panel de estado de pago.
patch(ReceiptScreen.prototype, {
  // Recargo IGTF de la orden en moneda principal (Bs). 0 en órdenes sin IGTF
  // o no facturadas — update_igtf() no lo calcula si !to_invoice — y ahí toda
  // esta pantalla se comporta exactamente como antes.
  get igtfAmount() {
    return Number(this.currentOrder?.get_igtf_amount?.()) || 0;
  },
  get igtfAmountLabel() {
    return this.env.utils.formatCurrency(this.igtfAmount);
  },
  get foreignIgtfAmountLabel() {
    return this.env.utils.formatForeignCurrency(
      this.currentOrder.get_foreign_igtf_amount()
    );
  },
  // Copia deliberada de point_of_sale/.../receipt_screen.js::orderAmountPlusTip
  // (Odoo 19) con el IGTF sumado al total: el core formatea la cadena dentro
  // del propio getter (y le concatena la propina), así que no hay forma de
  // componer sobre super(). Las órdenes sin IGTF delegan en super() arriba, de
  // modo que un cambio del core solo puede afectar a esta rama.
  // REVISAR EN CADA UPGRADE.
  get orderAmountPlusTip() {
    const igtf = this.igtfAmount;
    if (!igtf) {
      return super.orderAmountPlusTip;
    }
    const order = this.currentOrder;
    const tip_product_id = this.pos.config.tip_product_id?.id;
    const tipLine = order
      .getOrderlines()
      .find((line) => tip_product_id && line.product_id.id === tip_product_id);
    const tipAmount = tipLine ? tipLine.prices.total_included : 0;
    const orderAmountStr = this.env.utils.formatCurrency(
      order.priceIncl - tipAmount + igtf
    );
    if (!tipAmount) {
      return orderAmountStr;
    }
    const tipAmountStr = this.env.utils.formatCurrency(tipAmount);
    return `${orderAmountStr} + ${tipAmountStr} tip`;
  },
  // Sustituye el total foráneo que pinta l10n_ve_pos junto al total local.
  // Sin IGTF devuelve exactamente lo mismo que antes
  // (get_foreign_total_with_tax()), que sigue intacto como conversión pura de
  // factura para el resto de consumidores (recibo, ticket, backend).
  get foreignOrderAmountWithIgtf() {
    const order = this.currentOrder;
    const amount = this.igtfAmount
      ? order.get_foreign_total_paid_with_igtf()
      : order.get_foreign_total_with_tax();
    return this.env.utils.formatForeignCurrency(amount);
  },
});
