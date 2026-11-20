/** @odoo-module **/

import { PosPayment } from "@point_of_sale/app/models/pos_payment";
import { patch } from "@web/core/utils/patch";

patch(PosPayment.prototype, {
  /**
   * Código de la máquina fiscal del pago: el de la configuración del método
   * para la moneda con que pagó el cliente (`code_fiscal_printer` en
   * `pos.payment.method.currency`) y, si no tiene, el del método. Con un solo
   * efectivo para bolívares, dólares y euros (ADR-023) el código ya no puede
   * salir solo del método.
   */
  get fiscalPrinterCode() {
    return (
      this.currencySettings?.code_fiscal_printer ||
      this.payment_method_id?.code_fiscal_printer ||
      false
    );
  },
});
