/** @odoo-module */

import { OrderReceipt } from "@point_of_sale/app/screens/receipt_screen/receipt/order_receipt";
import { formatCurrency } from "@web/core/currency";
import { patch } from "@web/core/utils/patch";

patch(OrderReceipt, {
    props: {
      ...OrderReceipt.props,
      formatForeignCurrency: Function,
    },
});

patch(OrderReceipt.prototype, {
    // Pago en una moneda de cobro (p. ej. EUR): lo que pagó el cliente en esa
    // moneda, junto al nombre del método; el monto de la línea sigue en la
    // moneda de la caja. Cadena vacía si la línea no tiene moneda de cobro.
    formatTenderAmount(line) {
        const currency = line?.getTenderCurrency?.();
        if (!currency) {
            return "";
        }
        return formatCurrency(line.getTenderAmount(), currency.id);
    },
});
