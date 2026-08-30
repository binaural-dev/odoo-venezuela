import { patch } from "@web/core/utils/patch";
import { LandingPage } from "@pos_self_order/app/pages/landing_page/landing_page";

patch(LandingPage.prototype, {
    /**
     * In Kiosk mode, l10n_ve_pos bills every order to a real customer
     * (to_invoice=True, SENIAT), so the customer must be identified by cédula
     * before building the order. Intercept start() to route to the
     * identification screen when the current order has no partner yet.
     *
     * Gated STRICTLY by self_ordering_mode === "kiosk" so the mobile/QR table
     * flow is untouched. The native draft-order early return of start() is
     * preserved (we don't intercept while it applies).
     */
    start() {
        const config = this.selfOrder.config;
        const draftEarlyReturn =
            this.draftOrder.length > 0 && config.self_ordering_pay_after === "each";
        if (
            config.self_ordering_mode === "kiosk" &&
            !draftEarlyReturn &&
            !this.selfOrder.currentOrder.partner_id
        ) {
            this.router.navigate("identification");
            return;
        }
        return super.start();
    },
});
