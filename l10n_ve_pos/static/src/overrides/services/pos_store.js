/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { ConnectionLostError } from "@web/core/network/rpc";
import { _t } from "@web/core/l10n/translation";

patch(PosStore.prototype, {
  async pay() {
    if (!(await this._checkOrderBeforePayment(this.getOrder()))) {
      return;
    }
    return await super.pay(...arguments);
  },

  // El pago rápido (use_fast_payment) valida la orden sin pasar por pay():
  // las mismas verificaciones, antes de imprimir en la MF.
  async validateOrderFast() {
    if (!(await this._checkOrderBeforePayment(this.getOrder()))) {
      return;
    }
    return await super.validateOrderFast(...arguments);
  },

  /**
   * Verificaciones antes de cobrar. Muestra el aviso y devuelve false si la
   * orden no se puede cobrar.
   */
  async _checkOrderBeforePayment(order) {
    if (!order) {
      return true;
    }
    // Bloquea el paso a la pantalla de pago si hay líneas con cantidad en 0:
    // no se puede cobrar/facturar un producto sin cantidad. Se listan los
    // nombres para que el cajero los elimine o corrija antes de continuar.
    const zeroQtyLines = order.lines.filter((line) => line.getQuantity() === 0);
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
      return false;
    }
    if (this.config.amount_to_zero) {
      const shortages = await this._getStockShortages(order);
      if (shortages.length) {
        const formatQty = (qty) => this.env.utils.formatProductQty(qty, false);
        const productLines = shortages
          .map(
            (shortage) =>
              `• ${shortage.name}: ${_t("ordered %(requested)s, on hand %(available)s", {
                requested: formatQty(shortage.requested),
                available: formatQty(shortage.available),
              })}`
          )
          .join("\n");
        this.dialog.add(AlertDialog, {
          title: _t("Insufficient stock"),
          body: _t(
            "There is not enough stock in the warehouse for:\n\n%s\n\nAdjust the quantities to continue with the payment.",
            productLines
          ),
        });
        return false;
      }
    }
    return true;
  },

  /**
   * "Cantidad en 0" (amount_to_zero): productos almacenables cuya cantidad en
   * la orden supera el stock a mano del almacén de la caja. Las líneas
   * negativas (devoluciones) no cuentan: devuelven stock.
   */
  async _getStockShortages(order) {
    const qtyByProduct = {};
    for (const line of order.lines) {
      const qty = line.getQuantity();
      if (qty <= 0) {
        continue;
      }
      const productId = line.getProduct().id;
      qtyByProduct[productId] = (qtyByProduct[productId] || 0) + qty;
    }
    if (!Object.keys(qtyByProduct).length) {
      return [];
    }
    try {
      return await this.data.call("pos.config", "check_stock_availability", [
        [this.config.id],
        qtyByProduct,
      ]);
    } catch (error) {
      if (!(error instanceof ConnectionLostError)) {
        throw error;
      }
      // Sin conexión: aproximación con el stock cargado al abrir la caja
      // (puede estar desactualizado y se calcula por almacén, no por la
      // ubicación origen de la caja).
      return Object.entries(qtyByProduct)
        .map(([productId, requested]) => ({
          product: this.models["product.product"].get(parseInt(productId)),
          requested,
        }))
        .filter(({ product, requested }) => {
          if (!product?.is_storable) {
            return false;
          }
          const rounding = product.uom_id?.rounding || 0.01;
          return requested - product.qty_available > rounding / 2;
        })
        .map(({ product, requested }) => ({
          name: product.display_name,
          requested,
          available: product.qty_available,
        }));
    }
  },
});
