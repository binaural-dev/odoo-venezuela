import { patch } from "@web/core/utils/patch";
import { ClosePosPopup } from "@point_of_sale/app/components/popups/closing_popup/closing_popup";

patch(ClosePosPopup.prototype, {
    async closeSession() {
        await this.pos.data.call("pos.session", "update_closing_notes", [
            this.pos.session.id,
            this.state.notes,
        ]);
        return super.closeSession(...arguments);
    },
});
