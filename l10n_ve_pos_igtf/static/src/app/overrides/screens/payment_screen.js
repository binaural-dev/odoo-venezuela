import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";
import { onWillStart } from "@odoo/owl";

patch(PaymentScreen.prototype, {
  setup() {
    super.setup(...arguments);
    // A refund gives back the IGTF of its sale: read what its original orders
    // charged before the screen renders, so the due of the refund and the
    // preload of its first line already include it.
    onWillStart(async () => {
      await this._loadRefundIgtfData();
    });
  },
  async _loadRefundIgtfData() {
    const order = this.currentOrder;
    if (!order || !order.isRefund) {
      return;
    }
    const originIds = new Set();
    for (const line of order.lines || []) {
      const id = line.refunded_orderline_id?.order_id?.id;
      if (id) {
        originIds.add(id);
      }
    }
    if (!originIds.size) {
      return;
    }
    try {
      const data = await this.orm.call("pos.order", "get_refund_igtf_data", [
        Array.from(originIds),
      ]);
      order.refund_igtf_data = Object.fromEntries(
        (data || []).map((origin) => [origin.id, origin])
      );
    } catch (error) {
      // Without the IGTF of the sale the refund computes it from its payment
      // lines, as before.
      console.warn("[l10n_ve_pos_igtf] no se pudo leer el IGTF de la orden original:", error);
      return;
    }
    order.update_igtf();
  },
  async addNewPaymentLine(paymentMethod) {
    // Sin caso especial para apply_igtf: la precarga es remainingDue (deuda
    // de factura + deuda IGTF acumulada) y la maneja l10n_ve_pos, que además
    // formatea el numberBuffer con locale. El IGTF que genere esta línea nace
    // en update_igtf() como nuevo restante (diseño 2026-07-09). El clamp
    // IGTF-aware de set_foreign_amount (payment_model.js) evita el drift.
    const res = await super.addNewPaymentLine(...arguments);
    this.currentOrder.update_igtf();
    return res;
  },
  updateSelectedPaymentline(amount = false) {
    super.updateSelectedPaymentline(amount);
    this.currentOrder.update_igtf();
  },
  async toggleIsToInvoice() {
    await super.toggleIsToInvoice();
    this.currentOrder.update_igtf();
  },
  deletePaymentLine(uuid) {
    super.deletePaymentLine(uuid);
    this.currentOrder.update_igtf();
  },
});
