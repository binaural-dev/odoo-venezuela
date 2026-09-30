from odoo import api, models, tools

from .mail_bounce_event import SKIP_NATIVE_AUTO_BLACKLIST


class MailBlacklist(models.Model):
    _inherit = 'mail.blacklist'

    def _add(self, email, message=None):
        # neutralize the hardcoded rule of mass_mailing, see mail.thread override
        if self.env.context.get(SKIP_NATIVE_AUTO_BLACKLIST):
            return self.browse()
        return super()._add(email, message=message)

    def write(self, vals):
        removed_emails = []
        if 'active' in vals and not vals['active']:
            removed_emails = self.filtered('active').mapped('email')
        res = super().write(vals)
        if removed_emails:
            self.env['mail.bounce.event']._reset_failures(removed_emails)
        return res

    def unlink(self):
        removed_emails = self.filtered('active').mapped('email')
        res = super().unlink()
        if removed_emails:
            self.env['mail.bounce.event']._reset_failures(removed_emails)
        return res

    @api.model
    def _get_blacklisted_emails(self, emails):
        """ Return the subset of normalized ``emails`` that are actively blacklisted. """
        normalized_emails = list({tools.email_normalize(email) for email in emails} - {False})
        if not normalized_emails:
            return set()
        self.flush_model(['email', 'active'])
        self.env.cr.execute(
            "SELECT email FROM mail_blacklist WHERE active = true AND email = ANY(%s)",
            (normalized_emails,),
        )
        return {row[0] for row in self.env.cr.fetchall()}
