import { patch } from "@web/core/utils/patch";
import { ProductCard } from "@pos_self_order/app/components/product_card/product_card";

patch(ProductCard.prototype, {
    selectProduct() {
        const result = super.selectProduct(...arguments);
        // Reset the search after adding a simple product so the next scan/search
        // starts from a clean box in the scan / search only mode (configurable
        // and combo products navigate away).
        this.selfOrder.kioskOnProductSelected?.();
        return result;
    },
});
