/** @odoo-module **/

import AppointmentAffiliateToggle from "@binaural_memberships/js/appointment_affiliate_toggle"; 
import { jsonrpc } from "@web/core/network/rpc_service";
import { _t } from "@web/core/l10n/translation";

AppointmentAffiliateToggle.include({
    
    selector: '#addAffiliateModal, #addGuestModal, .o_appointment_validation_details',

    events: Object.assign({}, AppointmentAffiliateToggle.prototype.events, {
        'click .js_delete_guest': '_onDeleteGuest',
    }),

    /**
     * New method to delete a guest and remove them from HikCentral
     */
    async _onDeleteGuest(ev) {
        ev.preventDefault();
        const $btn = $(ev.currentTarget);

        if ($btn.prop('disabled')) return;

        if (!confirm(_t("You sure that you want to delete this guest from the appointment?"))) {
            return;
        }

        const guestId = $btn.data('guest-id');
        const token = this.accessToken || $btn.data('access-token');

        if (!guestId || !token) {
            console.error("Missing data (guestId or token)");
            return;
        }

        const originalHtml = $btn.html();
        $btn.prop('disabled', true).html('<i class="fa fa-spinner fa-spin"></i>');

        try {
            const result = await jsonrpc('/appointment/guest/delete_json', {
                access_token: token,
                guest_id: parseInt(guestId)
            });

            if (result.success) {
                window.location.reload();
            } else {
                throw new Error(result.error || "Error desconocido");
            }

        } catch (error) {
            console.error(error);
            $btn.prop('disabled', false).html(originalHtml);
            
            let msg = error.message;
            if (error.data && error.data.message) msg = error.data.message;
            alert(_t("Error al eliminar: ") + msg);
        }
    }
});