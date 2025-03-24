/** @odoo-module */

import { OrderWidget } from "@point_of_sale/app/generic_components/order_widget/order_widget";
import { patch } from "@web/core/utils/patch";

patch(OrderWidget, {
  props: {
    ...OrderWidget.props,
    conversion_rate: { optional: true },
    foreign_total: { type: String, optional: true },
    foreign_tax: { type: String, optional: true },
    quantity_products: { optional: true },
  },
});
