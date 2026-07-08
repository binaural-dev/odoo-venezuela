/** @odoo-module **/

import { DiscountButton } from "@pos_discount/overrides/components/discount_button/discount_button";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";

/**
 * Fix: el descuento global de `pos_discount` calculaba `baseToDiscount`
 * (via `order.calculate_base_amount`) sobre los precios de línea YA
 * descontados (por una asignación de descuento global anterior). Esto
 * producía una tasa final incorrecta al reasignar el descuento después de
 * agregar una línea nueva (ej: 15% seguido de 20% resultaba en ~18% en
 * vez de 20% en todas las líneas).
 *
 * Fix: resetear el descuento de todas las líneas (excepto las excluidas
 * por `isGlobalDiscountApplicable`, ej. propina) a 0% ANTES de calcular
 * `baseToDiscount`. Así la base siempre es el precio crudo del producto,
 * y el porcentaje ingresado por el usuario se aplica exactamente sobre
 * esa base. La distribución final del descuento sobre cada línea la hace
 * `_applyGlobalDiscountBeforeValidation` en PosStore.js.
 */
patch(DiscountButton.prototype, {
    async apply_discount(pc) {
        const order = this.pos.get_order();
        const product = this.pos.db.get_product_by_id(this.pos.config.discount_product_id[0]);
        if (product === undefined) {
            await this.popup.add(ErrorPopup, {
                title: _t("No discount product found"),
                body: _t(
                    "The discount product seems misconfigured. Make sure it is flagged as 'Can be Sold' and 'Available in Point of Sale'."
                ),
            });
            return;
        }

        // Remove existing discount lines
        order
            .get_orderlines()
            .filter((line) => line.get_product() === product)
            .forEach((line) => order._unlinkOrderline(line));

        // Reset ALL line discounts to 0% BEFORE calculating base amounts,
        // so `calculate_base_amount` uses raw prices instead of prices
        // already discounted by a previous global discount assignment.
        for (const line of order.get_orderlines()) {
            if (line.isGlobalDiscountApplicable()) {
                line.set_discount(0);
            }
        }

        // Add one discount line per tax group (original pos_discount logic)
        const linesByTax = order.get_orderlines_grouped_by_tax_ids();
        for (const [tax_ids, lines] of Object.entries(linesByTax)) {
            const tax_ids_array = tax_ids
                .split(",")
                .filter((id) => id !== "")
                .map((id) => Number(id));

            const baseToDiscount = order.calculate_base_amount(
                tax_ids_array,
                lines.filter((ll) => ll.isGlobalDiscountApplicable())
            );

            const discount = (-pc / 100.0) * baseToDiscount;
            if (discount < 0) {
                order.add_product(product, {
                    price: discount,
                    lst_price: discount,
                    tax_ids: tax_ids_array,
                    merge: false,
                    description:
                        `${pc}%, ` +
                        (tax_ids_array.length
                            ? _t(
                                  "Tax: %s",
                                  tax_ids_array
                                      .map((taxId) => this.pos.taxes_by_id[taxId].amount + "%")
                                      .join(", ")
                              )
                            : _t("No tax")),
                    extras: {
                        price_type: "automatic",
                    },
                });
            }
        }
    },
});
