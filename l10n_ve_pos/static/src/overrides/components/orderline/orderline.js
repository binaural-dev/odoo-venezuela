/** @odoo-module */

import { Orderline } from "@point_of_sale/app/components/orderline/orderline";
import { patch } from "@web/core/utils/patch";
import { formatCurrency } from "@web/core/currency";
import { _t } from "@web/core/l10n/translation";

// Ticket 15725: el core no pinta el precio de las líneas hijas de un combo,
// solo el del padre (la suma de ellas). Cada hija muestra su parte del precio
// como una línea normal: su displayPrice en la moneda de la caja y, por
// orderline.xml, el monto secundario (foráneo o de la compañía).
// El descuento de la hija sigue oculto, como en el core (`discount: ... &&
// !line.combo_parent_id`): su displayPrice ya lo trae aplicado.
patch(Orderline.prototype, {
    get lineScreenValues() {
        const vals = super.lineScreenValues;
        const line = this.line;
        if (line.order_id && line.combo_parent_id && !this.props.basic_receipt) {
            vals.price =
                line.getDiscount() === 100
                    ? _t("Free")
                    : formatCurrency(line.displayPrice, line.currency.id);
        }
        return vals;
    },
});
