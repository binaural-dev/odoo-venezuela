/** @odoo-module */

import { OrderSummary } from "@point_of_sale/app/screens/product_screen/order_summary/order_summary";
import { patch } from "@web/core/utils/patch";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { formatMonetary } from "@web/views/fields/formatters";

patch(OrderSummary.prototype, {
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

  getConversionRateForDisplay() {
    const order = this.currentOrder;
    if (!order) {
      return _t("N/D");
    }

    const rateDp = this.pos?.models?.["decimal.precision"]?.find?.(
      (dp) => dp.name === "Tasa",
    );
    const ratePrecision = Number.isFinite(Number(rateDp?.digits))
      ? Number(rateDp.digits)
      : 6;
    const configRate = Number(this.pos?.config?.foreign_rate || order?.config?.foreign_rate || 0);
    if (Number.isFinite(configRate) && configRate > 0) {
      const normalizedConfigRate = configRate < 1 ? 1 / configRate : configRate;
      return formatMonetary(normalizedConfigRate, { digits: [false, ratePrecision], noSymbol: true });
    }

    const conversionRate = order.get_conversion_rate?.();
    const numericRate = Number(conversionRate);
    const fallbackVisualRate = Number.isFinite(numericRate) && numericRate > 0
      ? (numericRate < 1 ? 1 / numericRate : numericRate)
      : conversionRate;
    const roundedVisualRate = Number.isFinite(fallbackVisualRate)
      ? Number((fallbackVisualRate + Number.EPSILON).toFixed(ratePrecision))
      : fallbackVisualRate;
    const visualRate = Number.isFinite(roundedVisualRate)
      ? formatMonetary(roundedVisualRate, { digits: [false, ratePrecision], noSymbol: true })
      : roundedVisualRate;
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

    return visualRate;
  },
});
