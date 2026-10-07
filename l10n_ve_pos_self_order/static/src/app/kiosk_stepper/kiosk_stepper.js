import { Component } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { useSelfOrder } from "@pos_self_order/app/services/self_order_service";
import { _t } from "@web/core/l10n/translation";

// Maps the self_order router's activeSlot to the stepper's step number.
// Slots not listed here (e.g. "default", "location", "stand_number") hide
// the stepper.
const STEP_BY_SLOT = {
    identification: 1,
    product_list: 2,
    product: 2,
    combo_selection: 2,
    cart: 2,
    payment: 3,
};

const STEPS = [
    { number: 1, label: _t("Identification") },
    { number: 2, label: _t("Scan") },
    { number: 3, label: _t("Payment") },
];

export class KioskStepper extends Component {
    static template = "l10n_ve_pos_self_order.KioskStepper";
    static props = {};

    setup() {
        this.selfOrder = useSelfOrder();
        this.router = useService("router");
    }

    get steps() {
        return STEPS;
    }

    // 1/2/3 for the step matching the active screen, "done" once the order
    // reaches confirmation, or null (hides the bar) on the welcome screen or
    // any slot outside the kiosk flow.
    get step() {
        const slot = this.router.activeSlot;
        if (slot === "confirmation") {
            return "done";
        }
        return STEP_BY_SLOT[slot] || null;
    }

    stepState(stepNumber) {
        const current = this.step;
        if (current === "done") {
            return "done";
        }
        if (current === stepNumber) {
            return "active";
        }
        if (current > stepNumber) {
            return "done";
        }
        return "next";
    }
}
