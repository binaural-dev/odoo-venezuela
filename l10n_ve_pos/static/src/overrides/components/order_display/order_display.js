import { OrderDisplay } from "@point_of_sale/app/components/order_display/order_display";
import { patch } from "@web/core/utils/patch";
import { usePos } from "@point_of_sale/app/hooks/pos_hook";

patch(OrderDisplay.prototype, {
  setup() {
    super.setup(...arguments);
    this.pos = usePos();
  },

  get conversionRateText() {
    return this.order.get_display_rate_formatted();
  },

  get quantityProducts() {
    return this.order.get_qty_products();
  },

  get foreignTotalText() {
    return this.pos.formatForeignCurrency(this.order.get_foreign_total_with_tax());
  },

  get foreignTaxText() {
    return this.pos.formatForeignCurrency(this.order.get_foreign_total_tax());
  },
});
