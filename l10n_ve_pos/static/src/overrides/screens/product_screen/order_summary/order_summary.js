/** @odoo-module */

import { OrderSummary } from "@point_of_sale/app/screens/product_screen/order_summary/order_summary";
import { patch } from "@web/core/utils/patch";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { onWillRender } from "@odoo/owl";

patch(OrderSummary.prototype, {
  setup() {
    super.setup(...arguments);
    onWillRender(() => this._alertMissingConversionRate());
  },

  // Ticket 14352: la línea de descuento nunca queda positiva. La coacción de
  // signo vive en el modelo (`PosOrderline.setUnitPrice`), para que el
  // cajero pueda cambiar el monto sin recibir una alerta en cada tecla. Acá
  // solo se cubre un caso que el modelo no puede resolver por sí solo: "+/-"
  // con el buffer recién limpio (ver `_shouldSkipDiscountLineSignToggle`).

  // "+/-" con el buffer recién limpio, en modo precio, sobre la línea de
  // descuento: el core arma el nuevo monto desde
  // `selectedLine.prices.total_excluded_currency` (sin impuesto) en vez de
  // `price_unit`. La línea de descuento lleva un impuesto tax-included, así
  // que ese monto NO es el mismo: se encoge por el factor del impuesto
  // (p. ej. -5.617,52 → -4.842,69 con 16% IVA). Como el modelo ya garantiza
  // que esta línea nunca queda positiva (`setUnitPrice`), "+/-" no tiene
  // signo que invertir. Separado de `updateSelectedOrderline` para poder
  // testear la condición sin depender del `super` (que necesita un entorno
  // completo: `dialog`, `numberBuffer` real, etc.).
  _shouldSkipDiscountLineSignToggle(selectedLine, { buffer, key }) {
    return Boolean(
      buffer === "-0" &&
        key === "-" &&
        this.pos.numpadMode === "price" &&
        selectedLine?._isDiscountProductLine?.() &&
        !selectedLine._isRefundLine?.()
    );
  },

  async updateSelectedOrderline({ buffer, key }) {
    const order = this.pos.getOrder();
    const selectedLine = order?.getSelectedOrderline();
    if (this._shouldSkipDiscountLineSignToggle(selectedLine, { buffer, key })) {
      this.numberBuffer.reset();
      return;
    }
    return super.updateSelectedOrderline(...arguments);
  },

  _alertMissingConversionRate() {
    const order = this.currentOrder;
    if (!order || order._missingConversionRateAlertShownInUI) {
      return;
    }
    if (order.get_display_rate() !== _t("N/D")) {
      return;
    }
    order._missingConversionRateAlertShownInUI = true;
    this.dialog.add(AlertDialog, {
      title: _t("Tasa de conversión faltante"),
      body: _t(
        "No se puede calcular la tasa porque faltan valores. Configura una tasa de conversión en la configuración de la empresa para poder calcularla.",
      ),
    });
  },

  _setValue(val) {
    const { numpadMode } = this.pos;
    const order = this.currentOrder;
    const selectedLine = order.getSelectedOrderline();
    if (!selectedLine) {
      this.numberBuffer.reset();
      const lines = order.getOrderlines();
      if (lines.length > 0 && (val == "" || val == "remove")) {
        order.selectOrderline(lines[lines.length - 1]);
        return;
      }
      return super._setValue(val);
    }
    if (numpadMode === "quantity" && (val === "0" || val == "" || val === "remove")) {
      this.numberBuffer.reset();
      order.removeOrderline(selectedLine);
      order.deselectOrderline();
      return;
    }
    return super._setValue(val);
  },
});
