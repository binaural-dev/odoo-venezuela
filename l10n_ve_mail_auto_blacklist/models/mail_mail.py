import re

from odoo import models, tools, _

# SMTP errors attributable to the recipient address (not to our server):
# SMTPRecipientsRefused, 550-553 permanent errors, 5.1.x "bad destination" codes
RECIPIENT_REFUSED_RE = re.compile(r'SMTPRecipientsRefused|\b55[0-3]\b|\b5\.1\.\d\b', re.IGNORECASE)


class MailMail(models.Model):
    _inherit = 'mail.mail'

    def _auto_blacklist_get_recipient_emails(self):
        """ Normalized emails of every recipient (To, Cc, partners) of the mail. """
        self.ensure_one()
        emails = set(tools.mail.email_normalize_all(self.email_to or ''))
        emails.update(tools.mail.email_normalize_all(self.email_cc or ''))
        for partner in self.recipient_ids:
            emails.update(tools.mail.email_normalize_all(partner.email or ''))
        return emails

    def _auto_blacklist_cancel_blocked_mails(self):
        """ Cancel outgoing mails whose recipients are all blacklisted, whatever
        their origin (mass mailing or transactional). """
        outgoing = self.filtered(lambda mail: mail.state == 'outgoing')
        recipients_by_mail = {mail: mail._auto_blacklist_get_recipient_emails() for mail in outgoing}
        blacklisted = self.env['mail.blacklist']._get_blacklisted_emails(set().union(*recipients_by_mail.values()))
        if not blacklisted:
            return self.browse()
        blocked_mails = self.browse([
            mail.id for mail, emails in recipients_by_mail.items() if emails and emails <= blacklisted
        ])
        if blocked_mails:
            blocked_mails.write({
                'state': 'cancel',
                'failure_type': 'mail_bl',
                'failure_reason': _('All recipients are in the email blacklist.'),
            })
            self.env['mail.notification'].sudo().search([
                ('notification_type', '=', 'email'),
                ('mail_mail_id', 'in', blocked_mails.ids),
                ('notification_status', 'not in', ('sent', 'canceled')),
            ]).write({'notification_status': 'canceled', 'failure_type': 'mail_bl'})
            blocked_mails.mailing_trace_ids.write({'trace_status': 'cancel', 'failure_type': 'mail_bl'})
        return blocked_mails

    def _send(self, *args, **kwargs):
        if self.env['mail.bounce.event']._is_auto_blacklist_enabled():
            self._auto_blacklist_cancel_blocked_mails()
        return super()._send(*args, **kwargs)

    def _prepare_outgoing_list(self, mail_server=False, doc_to_followers=None):
        """ Remove blacklisted addresses from mails having only some of their
        recipients blacklisted (fully blocked mails are canceled in ``_send``). """
        email_list = super()._prepare_outgoing_list(mail_server=mail_server, doc_to_followers=doc_to_followers)
        if not self.env['mail.bounce.event']._is_auto_blacklist_enabled():
            return email_list
        blacklisted = self.env['mail.blacklist']._get_blacklisted_emails(
            {email for values in email_list for email in values['email_to_normalized']}
        )
        if not blacklisted:
            return email_list

        def _allowed(addresses):
            return [address for address in addresses if tools.email_normalize(address) not in blacklisted]

        filtered_list = []
        blocked_partners = self.env['res.partner']
        for values in email_list:
            email_to, email_cc = _allowed(values['email_to']), _allowed(values['email_cc'])
            if not email_to and not email_cc:
                blocked_partners |= values['partner_id'] or self.env['res.partner']
                continue
            values.update({
                'email_to': email_to,
                'email_cc': email_cc,
                'email_to_normalized': [email for email in values['email_to_normalized'] if email not in blacklisted],
            })
            filtered_list.append(values)
        if blocked_partners:
            self.env['mail.notification'].sudo().search([
                ('notification_type', '=', 'email'),
                ('mail_mail_id', '=', self.id),
                ('res_partner_id', 'in', blocked_partners.ids),
            ]).write({'notification_status': 'canceled', 'failure_type': 'mail_bl'})
        return filtered_list

    def _postprocess_sent_message(self, success_pids, success_emails, failure_reason=False, failure_type=None):
        """ Count SMTP refusals of recipient addresses as delivery failures. Only
        addresses quoted in the SMTP error are counted, so that a server problem
        or a mail with several recipients does not blacklist everybody. """
        if failure_type and failure_reason and RECIPIENT_REFUSED_RE.search(failure_reason):
            reason = failure_reason.lower()
            succeeded = {tools.email_normalize(email) for email in success_emails or []}
            failed = {
                email
                for mail in self
                for email in mail._auto_blacklist_get_recipient_emails()
                if email not in succeeded
                and re.search(r'(?<![\w.+-])%s(?![\w-])(?!\.\w)' % re.escape(email), reason)
            }
            if failed:
                BounceEvent = self.env['mail.bounce.event']
                # A synchronous recipient refusal is, by definition of
                # RECIPIENT_REFUSED_RE, already a recipient-level problem (not a
                # generic server hiccup) -- default to 'hard' when the reason
                # text itself doesn't carry an explicit 4xx/5xx signal.
                BounceEvent._register_failures(
                    failed, 'smtp_error', reason=failure_reason[:2000],
                    bounce_type=BounceEvent._classify_bounce_type(failure_reason, default='hard'),
                )
        return super()._postprocess_sent_message(
            success_pids, success_emails, failure_reason=failure_reason, failure_type=failure_type,
        )
