/** @odoo-module **/

import { OrderDisplay } from "@point_of_sale/app/components/order_display/order_display";
import { patch } from "@web/core/utils/patch";
import { onWillUpdateProps, onWillStart, onMounted } from "@odoo/owl";
patch(OrderDisplay, {
  props: {
    ...OrderDisplay.props,
    conversion_rate: { optional: true },
    foreign_total: { optional: true },
    foreign_tax: { optional: true },
    quantity_products: { optional: true },
  },
});

// patch(OrderDisplay.prototype, {
//   setup() {
//     // A. SIEMPRE llamar al padre primero para no romper el POS
//     super.setup(...arguments);
//     onWillUpdateProps((nextProps) => {
//       console.log("Cambiaron las props. El nuevo total es:", nextProps);
//       // nextProps.map((key, item) =>
//       //   console.log("ITEM IS", item)
//       // )
//     });
//   }
// });