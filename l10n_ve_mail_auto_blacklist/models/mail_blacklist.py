from odoo import api, fields, models, tools
from odoo.tools.safe_eval import safe_eval

from .mail_bounce_event import BOUNCE_TYPE_SELECTION, SKIP_NATIVE_AUTO_BLACKLIST


class MailBlacklist(models.Model):
    _inherit = 'mail.blacklist'

    l10n_ve_bounce_event_count = fields.Integer(
        'Delivery Failures', compute='_compute_l10n_ve_bounce_info',
        help='Number of recorded bounces/SMTP refusals for this address.')
    l10n_ve_last_bounce_type = fields.Selection(
        BOUNCE_TYPE_SELECTION, string='Last Bounce Type', compute='_compute_l10n_ve_bounce_info',
        help='Severity of the most recent delivery failure for this address: '
             'Hard (permanent, e.g. unknown domain/user) or Soft (temporary, e.g. full mailbox).')

    def _compute_l10n_ve_bounce_info(self):
        # No sudo(): mail.blacklist and mail.bounce.event share the same read
        # groups (mass_mailing.group_mass_mailing_user / base.group_system), so
        # anyone able to open this list already has access to the other model.
        BounceEvent = self.env['mail.bounce.event']
        emails = list({rec.email for rec in self if rec.email})
        counts, last_types = {}, {}
        if emails:
            counts = dict(BounceEvent._read_group([('email', 'in', emails)], ['email'], ['__count']))
            # One query for everyone, not one search() per email (N+1): order by
            # email then most-recent-first and keep only the first row per email.
            for event in BounceEvent.search([('email', 'in', emails)], order='email, event_date desc, id desc'):
                last_types.setdefault(event.email, event.bounce_type)
        for rec in self:
            rec.l10n_ve_bounce_event_count = counts.get(rec.email, 0)
            rec.l10n_ve_last_bounce_type = last_types.get(rec.email, False)

    def action_l10n_ve_view_bounce_events(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('l10n_ve_mail_auto_blacklist.mail_bounce_event_action')
        action['domain'] = [('email', '=', self.email)]
        # action['context'] is still the raw stored string (e.g.
        # "{'search_default_group_by_email': 1}"), not a dict -- evaluate it
        # before merging, or override the whole action context by mistake.
        context = safe_eval(action.get('context') or '{}')
        action['context'] = dict(context, search_default_group_by_email=0)
        return action

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
