import { patch } from "@web/core/utils/patch";
import { selfOrderIndex } from "@pos_self_order/app/self_order_index";
import { KioskStepper } from "@l10n_ve_pos_self_order/app/kiosk_stepper/kiosk_stepper";

// Register KioskStepper so self_order_index_stepper.xml can mount it.
patch(selfOrderIndex, {
    components: {
        ...selfOrderIndex.components,
        KioskStepper,
    },
});
