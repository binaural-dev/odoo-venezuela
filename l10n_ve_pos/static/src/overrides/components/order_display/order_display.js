/** @odoo-module **/

import { OrderDisplay } from "@point_of_sale/app/components/order_display/order_display";
import { patch } from "@web/core/utils/patch";

patch(OrderDisplay, {
  props: {
    ...OrderDisplay.props,
    conversion_rate: { optional: true },
    foreign_total: { type: String, optional: true },
    foreign_tax: { type: String, optional: true },
    quantity_products: { optional: true },
  },
});
