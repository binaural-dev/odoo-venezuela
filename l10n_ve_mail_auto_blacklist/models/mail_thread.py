from odoo import api, models, tools

from .mail_bounce_event import SKIP_NATIVE_AUTO_BLACKLIST

# Content-types worth reading as text when looking for a classification signal.
# Attachments (images, PDFs...) are deliberately excluded: decoding binary data
# as text with errors="replace" lets through valid ASCII bytes (digits
# included) and can produce a false SMTP code match by sheer chance.
_BOUNCE_READABLE_CONTENT_TYPES = ('text/plain', 'text/html', 'message/delivery-status', 'message/rfc822-headers')
# DSN (RFC 3464) fields: the email package parses them as HEADERS of a nested
# per-recipient sub-part, not as that part's payload/body, so they must be
# read with part.get(field) -- get_payload() would miss them entirely.
_DSN_HEADER_FIELDS = ('Action', 'Status', 'Diagnostic-Code', 'Final-Recipient')


class MailThread(models.AbstractModel):
    _inherit = 'mail.thread'

    @api.model
    def _l10n_ve_extract_bounce_text(self, email_message):
        """ Concatenate the readable text of ``email_message`` (its text/plain
        and text/html parts) with any DSN field found on any of its parts, so
        ``mail.bounce.event._classify_bounce_type`` has a single blob of text
        to search regardless of how the bounce happens to be structured. """
        if email_message is None:
            return ''
        texts = []
        parts = email_message.walk() if email_message.is_multipart() else [email_message]
        for part in parts:
            if part.get_content_maintype() == 'multipart':
                continue
            if part.get_content_type() in _BOUNCE_READABLE_CONTENT_TYPES:
                payload = part.get_payload(decode=True)
                if payload:
                    texts.append(payload.decode(errors='replace'))
            for field in _DSN_HEADER_FIELDS:
                value = part.get(field)
                if value:
                    texts.append('%s: %s' % (field, value))
        return '\n'.join(texts)

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
            bounce_text = self._l10n_ve_extract_bounce_text(email_message)
            BounceEvent._register_failures(
                [bounced_email], 'bounce',
                reason=tools.html2plaintext(message_dict.get('body') or '')[:2000],
                bounce_type=BounceEvent._classify_bounce_type(bounce_text),
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
