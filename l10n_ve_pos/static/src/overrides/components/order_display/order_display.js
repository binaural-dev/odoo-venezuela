/** @odoo-module **/

import { OrderDisplay } from "@point_of_sale/app/components/order_display/order_display";
import { patch } from "@web/core/utils/patch";

patch(OrderDisplay, {
  props: {
    ...OrderDisplay.props,
    conversion_rate: { optional: true },
    foreign_inverse_rate: { optional: true },
    foreign_total_with_taxes: { optional: true },
    foreign_total_tax: { optional: true },
    foreign_tax_total: { optional: true },
    quantity_products: { optional: true },
  },
});