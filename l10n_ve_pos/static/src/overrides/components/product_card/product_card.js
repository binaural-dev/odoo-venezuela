/** @odoo-module */

import { usePos } from "@point_of_sale/app/store/pos_hook";
import { ProductCard } from "@point_of_sale/app/generic_components/product_card/product_card";
import { patch } from "@web/core/utils/patch";

patch(ProductCard, {
  props: {
    ...ProductCard.props,
    qty_available: { optional: true },
  },
});

patch(ProductCard.prototype, {
  setup() {
    this.pos = usePos();
  },
  get show_free_qty() {
    return this.pos.config.pos_show_free_qty
  }
});
