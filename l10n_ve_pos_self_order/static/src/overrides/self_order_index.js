import { patch } from "@web/core/utils/patch";
import { selfOrderIndex } from "@pos_self_order/app/self_order_index";
import { IdentificationPage } from "@l10n_ve_pos_self_order/app/pages/identification_page/identification_page";

// Register IdentificationPage so the new "identification" slot added to
// pos_self_order.selfOrderIndex can resolve the component.
patch(selfOrderIndex, {
    components: {
        ...selfOrderIndex.components,
        IdentificationPage,
    },
});
