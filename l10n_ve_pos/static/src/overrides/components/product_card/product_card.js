/** @odoo-module **/

import { ProductCard } from "@point_of_sale/app/components/product_card/product_card";
import { patch } from "@web/core/utils/patch";
import { useState, useEffect } from "@odoo/owl";
import { useTrackedAsync } from "@point_of_sale/app/hooks/hooks";
import { debounce } from "@web/core/utils/timing";

patch(ProductCard.prototype, {
  setup() {
    this.state = useState({
      available_quantity: 0,
    });

    this.fetchStock = useTrackedAsync(
      (product) => this.pos.getProductInfo(product, 1),
      { keepLast: true }
    );

    const debouncedFetchStocks = debounce(async (productId) => {
      const product =
        this.pos?.db?.product_by_id?.[productId] ||
        this.props.product ||
        null;
      if (!product) {
        this.state.available_quantity = 0;
        return;
      }

      await this.fetchStock.call(product);
      if (this.fetchStock.status === "success" && this.fetchStock.result) {
        const info = this.fetchStock.result.productInfo;
        this.state.available_quantity = info?.warehouses?.[0]?.available_quantity ?? 0;
      } else if (this.fetchStock.status === "error") {
        this.state.available_quantity = 0;
      }
    }, 250);

    useEffect(
      () => {
        const productId = this.props.productId ?? this.props.product?.id ?? null;
        if (productId) debouncedFetchStocks(productId);
      },
      () => [this.props.productId, this.props.product?.id]
    );
  },

  get show_free_qty() {
    return this.pos?.config?.pos_show_free_qty;
  },

  get free_qty() {
    return Number(this.state.available_quantity) || 0;
  },

  get stockStatus() {
    return this.fetchStock?.status || "idle";
  },
});