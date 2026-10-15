import { patch } from "@web/core/utils/patch";
import { SelfOrderRouter } from "@pos_self_order/app/services/self_order_router_service";

patch(SelfOrderRouter.prototype, {
    /**
     * Keep a handle on the Owl env so navigate() can reach the self_order
     * service lazily. The router service cannot declare self_order as a
     * dependency (self_order already depends on the router), so we read it
     * from env.services at call time instead.
     */
    setup(env) {
        super.setup(env);
        this.env = env;
    },

    /**
     * Kiosk mode routes every barcode scan through here. On a scan the core
     * self_order_service adds the product and calls navigate("cart"); we
     * intercept that automatic cart navigation:
     *
     *   1. "scan / search only" (hide-catalog): swallow it so the customer
     *      stays on the scan screen (the order builds up in the in-place
     *      summary).
     *   2. Otherwise: a scan on the initial screen jumps straight to the cart,
     *      bypassing the cédula/RIF identification gate that lives only in
     *      LandingPage.start(). If the current order still has no customer, send
     *      the customer to the identification screen instead — the product just
     *      scanned stays in the order and shows up after identifying. This keeps
     *      every kiosk order billed to a real customer (l10n_ve_pos, SENIAT).
     *
     * `suppressScanCartNav` is set by ProductListPage while the scan screen is
     * mounted. Explicit user navigation to the cart (the Checkout button, via
     * ProductListPage.review) sets `_allowScanCartNav`, so it is let through.
     */
    navigate(routeName, routeParams = {}) {
        if (routeName === "cart" && !this._allowScanCartNav) {
            if (this.suppressScanCartNav) {
                this._allowScanCartNav = false;
                return;
            }
            const selfOrder = this.env?.services?.self_order;
            if (
                selfOrder?.config?.self_ordering_mode === "kiosk" &&
                !selfOrder.currentOrder?.partner_id
            ) {
                this._allowScanCartNav = false;
                return super.navigate("identification");
            }
        }
        this._allowScanCartNav = false;
        return super.navigate(routeName, routeParams);
    },
});
