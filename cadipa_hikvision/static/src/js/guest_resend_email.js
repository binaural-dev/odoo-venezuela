/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import { jsonrpc } from "@web/core/network/rpc_service";
import { _t } from "@web/core/l10n/translation";

publicWidget.registry.GuestResendEmail = publicWidget.Widget.extend({
    selector: '.js_guest_resend_email_form',
    events: {
        'submit': '_onSubmit',
        'input input[name="email"]': '_onInput',
    },

    /**
     * Clears error/success messages when the user starts correcting the email.
     */
    _onInput: function (ev) {
        const $btn = this.$('button[type="submit"]');
        const $feedback = this.$('.js_feedback_msg');
        
        $feedback.addClass('d-none').text('');
        $btn.prop('disabled', false).removeClass('btn-success btn-danger').addClass('btn-warning');
        if ($btn.find('.fa-exclamation-triangle').length) {
            $btn.html('<i class="fa fa-paper-plane me-1"></i> <span>Reenviar</span>');
        }
    },

    /**
     * Handles the submission asynchronously using jsonrpc.
     */
    async _onSubmit(ev) {
        ev.preventDefault();

        const $form = $(ev.currentTarget);
        const $btn = $form.find('button[type="submit"]');
        const $input = $form.find('input[name="email"]');
        const $feedback = $form.find('.js_feedback_msg');

        const originalContent = $btn.html();

        const accessToken = $form.data('token');
        const guestId = parseInt($form.data('guest-id'));
        const email = $input.val();

        try {
            $btn.html('<i class="fa fa-spinner fa-spin"></i> Enviando...');
            $btn.prop('disabled', true);

            const result = await jsonrpc('/appointment/guest/resend_email_json', {
                access_token: accessToken,
                guest_id: guestId,
                email: email,
            });

            if (result.error) {
                throw new Error(result.error);
            }

            if (result.success) {
                $btn.html('<i class="fa fa-check"></i> Enviado');
                $btn.removeClass('btn-warning').addClass('btn-success');
                $feedback.removeClass('d-none text-danger').addClass('text-success').text(result.msg);

                setTimeout(() => {
                    $form.closest('.modal').find('.btn-close').click();
                }, 2000);
            }

        } catch (error) {
            console.error(error);
            
            $btn.html('<i class="fa fa-exclamation-triangle"></i> Reintentar');
            $btn.prop('disabled', false).removeClass('btn-warning').addClass('btn-danger');

            let msg = error.message || _t("Connection error while validating the guest.");
            if (error.data && error.data.message) {
                msg = error.data.message;
            }

            $feedback.removeClass('d-none text-success').addClass('text-danger').text(msg);
        }
    },
});