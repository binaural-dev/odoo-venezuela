from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

from .mail_bounce_event import (
    DEFAULT_MIN_SPREAD_DAYS, DEFAULT_THRESHOLD, DEFAULT_WINDOW_DAYS, PARAM_PREFIX,
)


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    l10n_ve_auto_blacklist_enabled = fields.Boolean(
        'Configurable Auto Blacklist', config_parameter=PARAM_PREFIX + 'enabled',
        help='Replaces the native rule (5 bounces within 13 weeks, spread over more than one week) '
             'and blocks every outgoing email, including transactional ones, to blacklisted addresses.')
    l10n_ve_auto_blacklist_threshold = fields.Integer(
        'Failures Before Blacklist', config_parameter=PARAM_PREFIX + 'threshold', default=DEFAULT_THRESHOLD)
    l10n_ve_auto_blacklist_window_days = fields.Integer(
        'Period (days)', config_parameter=PARAM_PREFIX + 'window_days', default=DEFAULT_WINDOW_DAYS,
        help='Only failures of the last X days are counted. 0 = no time limit.')
    l10n_ve_auto_blacklist_min_spread_days = fields.Integer(
        'Minimum Spread (days)', config_parameter=PARAM_PREFIX + 'min_spread_days',
        default=DEFAULT_MIN_SPREAD_DAYS,
        help='Minimum number of days between the first and the last counted failure, to avoid '
             'blacklisting because of a temporary server issue. 0 = no constraint.')
    l10n_ve_auto_blacklist_count_smtp_errors = fields.Boolean(
        'Count SMTP Refusals', config_parameter=PARAM_PREFIX + 'count_smtp_errors',
        help='Also count emails refused by the SMTP server because of the recipient address '
             '(e.g. 550 mailbox unavailable), not only bounces received afterwards.')

    @api.constrains('l10n_ve_auto_blacklist_threshold', 'l10n_ve_auto_blacklist_window_days',
                    'l10n_ve_auto_blacklist_min_spread_days')
    def _check_l10n_ve_auto_blacklist_values(self):
        for settings in self.filtered('l10n_ve_auto_blacklist_enabled'):
            if settings.l10n_ve_auto_blacklist_threshold < 1:
                raise ValidationError(_('The number of failures before blacklisting must be at least 1.'))
            if settings.l10n_ve_auto_blacklist_window_days < 0 or settings.l10n_ve_auto_blacklist_min_spread_days < 0:
                raise ValidationError(_('Periods cannot be negative.'))
            if (settings.l10n_ve_auto_blacklist_window_days
                    and settings.l10n_ve_auto_blacklist_min_spread_days >= settings.l10n_ve_auto_blacklist_window_days):
                raise ValidationError(_('The minimum spread must be shorter than the counted period.'))
