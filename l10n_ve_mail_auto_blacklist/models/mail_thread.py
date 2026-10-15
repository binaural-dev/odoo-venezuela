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
    def _l10n_ve_find_recipient_dsn_block(self, parts, bounced_email):
        """ Return the DSN "per-recipient" fields (Action/Status/Diagnostic-Code)
        of the specific part whose ``Final-Recipient`` matches ``bounced_email``.

        A single DSN can carry one such block per original recipient (e.g. a
        mail sent to several addresses that all failed); without this, reading
        whichever ``Status:``/``Action:`` appears first in the whole message
        can pick up another recipient's severity instead of the one we are
        actually registering a failure for. """
        if not bounced_email:
            return None
        for part in parts:
            final_recipient = part.get('Final-Recipient')
            if not final_recipient or ';' not in final_recipient:
                continue
            candidate = tools.email_normalize(final_recipient.split(';', 1)[1].strip())
            if candidate and candidate == bounced_email:
                fields = [
                    '%s: %s' % (field, part.get(field))
                    for field in _DSN_HEADER_FIELDS if part.get(field)
                ]
                if fields:
                    return '\n'.join(fields)
        return None

    @api.model
    def _l10n_ve_extract_bounce_text(self, email_message, bounced_email=False):
        """ Text used to classify the bounce as soft/hard: the DSN block of
        ``bounced_email`` specifically when found (see
        ``_l10n_ve_find_recipient_dsn_block``), otherwise the readable text of
        the whole message (its text/plain and text/html parts) plus any DSN
        field found anywhere, for bounces without a standard DSN block at all
        (e.g. Gmail's own plain-text "domain not found" notice). """
        if email_message is None:
            return ''
        parts = list(email_message.walk()) if email_message.is_multipart() else [email_message]

        recipient_block = self._l10n_ve_find_recipient_dsn_block(parts, bounced_email)
        if recipient_block:
            return recipient_block

        texts = []
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
            bounce_text = self._l10n_ve_extract_bounce_text(email_message, bounced_email)
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
