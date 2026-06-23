/** @odoo-module */

import { OrderSummary } from "@point_of_sale/app/screens/product_screen/order_summary/order_summary";
import { patch } from "@web/core/utils/patch";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";

patch(OrderSummary.prototype, {
  getConversionRateForDisplay() {
    const order = this.currentOrder;
    if (!order) {
      return _t("N/D");
    }

    const conversionRate = order.get_conversion_rate?.();
    const isMissingRate = conversionRate === "N/D" || conversionRate === _t("N/D");

    if (isMissingRate && !order._missingConversionRateAlertShownInUI) {
      order._missingConversionRateAlertShownInUI = true;
      this.dialog.add(AlertDialog, {
        title: _t("Tasa de conversión faltante"),
        body: _t(
          "No se puede calcular la tasa porque faltan valores. Configura una tasa de conversión en la configuración de la empresa para poder calcularla.",
        ),
      });
    }

    return conversionRate;
  },
});
