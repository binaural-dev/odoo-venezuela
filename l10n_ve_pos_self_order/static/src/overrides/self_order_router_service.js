import { patch } from "@web/core/utils/patch";
import { SelfOrderRouter } from "@pos_self_order/app/services/self_order_router_service";

patch(SelfOrderRouter.prototype, {
    /**
     * Kiosk "scan / search only": scanning a barcode adds the product and then
     * navigates to "cart" (see pos_self_order self_order_service). In that mode
     * we keep the customer on the scan screen — the order builds up in the
     * in-place summary — so we swallow that automatic cart navigation.
     *
     * `suppressScanCartNav` is set by ProductListPage while the scan screen is
     * mounted. Explicit user navigation to the cart (the Checkout button, via
     * ProductListPage.review) sets `_allowScanCartNav` right before navigating,
     * so it is let through.
     */
    navigate(routeName, routeParams = {}) {
        if (routeName === "cart" && this.suppressScanCartNav && !this._allowScanCartNav) {
            this._allowScanCartNav = false;
            return;
        }
        this._allowScanCartNav = false;
        return super.navigate(routeName, routeParams);
    },
});
