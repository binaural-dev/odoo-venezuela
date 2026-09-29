/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";

patch(PosStore.prototype, {
  async pay() {
    const order = this.getOrder();
    // Bloquea el paso a la pantalla de pago si hay líneas con cantidad en 0:
    // no se puede cobrar/facturar un producto sin cantidad. Se listan los
    // nombres para que el cajero los elimine o corrija antes de continuar.
    const zeroQtyLines = order
      ? order.lines.filter((line) => line.getQuantity() === 0)
      : [];
    if (zeroQtyLines.length) {
      const productNames = zeroQtyLines
        .map((line) => `• ${line.getFullProductName()}`)
        .join("\n");
      this.dialog.add(AlertDialog, {
        title: _t("Productos con cantidad en 0"),
        body: _t(
          "Los siguientes productos tienen cantidad en 0:\n\n%s\n\nElimínalos o colócales la cantidad correcta para continuar con el pago.",
          productNames
        ),
      });
      return;
    }
    return await super.pay(...arguments);
  },
});
