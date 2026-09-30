from odoo import api, models, tools

from .mail_bounce_event import SKIP_NATIVE_AUTO_BLACKLIST


class MailThread(models.AbstractModel):
    _inherit = 'mail.thread'

    @api.model
    def _routing_handle_bounce(self, email_message, message_dict):
        """ Replace the hardcoded auto blacklist rule of mass_mailing by the
        configurable one. Bounces of transactional emails are counted too. """
        BounceEvent = self.env['mail.bounce.event']
        if not BounceEvent._is_auto_blacklist_enabled():
            return super()._routing_handle_bounce(email_message, message_dict)

        res = super(MailThread, self.with_context(**{SKIP_NATIVE_AUTO_BLACKLIST: True}))._routing_handle_bounce(
            email_message, message_dict,
        )
        if bounced_email := message_dict.get('bounced_email'):
            BounceEvent._register_failures(
                [bounced_email], 'bounce',
                reason=tools.html2plaintext(message_dict.get('body') or '')[:2000],
            )
        return res

    @api.model
    def _routing_reset_bounce(self, email_message, message_dict):
        """ An email received from an address proves it is valid: restart its
        failure counter, like Odoo does with ``message_bounce``. """
        res = super()._routing_reset_bounce(email_message, message_dict)
        if email_from := tools.email_normalize(message_dict.get('email_from')):
            self.env['mail.bounce.event']._reset_failures([email_from])
        return res
