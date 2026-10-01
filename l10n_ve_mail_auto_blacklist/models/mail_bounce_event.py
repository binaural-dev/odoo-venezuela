import re
from datetime import timedelta

from markupsafe import Markup

from odoo import api, fields, models, tools, _

PARAM_PREFIX = 'l10n_ve_mail_auto_blacklist.'
# Context key used to neutralize the hardcoded native rule of mass_mailing
# (5 bounces / 13 weeks / 1 week spread) while our configurable rule is active.
SKIP_NATIVE_AUTO_BLACKLIST = 'l10n_ve_skip_native_auto_blacklist'

DEFAULT_THRESHOLD = 5
DEFAULT_WINDOW_DAYS = 90
DEFAULT_MIN_SPREAD_DAYS = 0

BOUNCE_TYPE_SELECTION = [
    ('soft', 'Soft (Temporary)'),
    ('hard', 'Hard (Permanent)'),
]

# DSN (RFC 3464) fields, when the mail server that bounced the message followed
# the standard: the most reliable signal, used by Postfix, Exchange, Office365...
_STATUS_RE = re.compile(r'Status:\s*([45])\.(\d+\.\d+)', re.IGNORECASE)
_ACTION_RE = re.compile(r'Action:\s*(\w+)', re.IGNORECASE)
# Explicit SMTP reply code, when no full DSN block is present. Per RFC 5321
# any 5xx is permanent and any 4xx is temporary, not just the common ones.
_HARD_CODE_RE = re.compile(r'\b5\d{2}\b')
_SOFT_CODE_RE = re.compile(r'\b4\d{2}\b')
# Known phrases for bounces without any DSN/code at all (e.g. Gmail's own
# "domain not found" notice, which is plain text for a human, not a DSN).
_HARD_PHRASES = (
    'nxdomain', 'domain not found', 'no se ha encontrado el dominio', 'no existe el dominio',
    'user unknown', 'no such user', 'address not found', 'mailbox not found',
    'mailbox unavailable', 'recipient address rejected', 'no se ha encontrado la direcci',
    'does not exist', 'invalid recipient', 'unrouteable address', 'bad destination mailbox',
)
_SOFT_PHRASES = (
    'mailbox full', 'quota exceeded', 'try again later', 'temporarily deferred', 'greylist',
    'connection timed out', 'temporary failure', 'throttl', 'service unavailable',
    'buzón lleno', 'buzon lleno', 'inténtalo más tarde', 'intentalo mas tarde',
)


class MailBounceEvent(models.Model):
    """ One delivery failure (bounce or SMTP recipient refusal) for one email
    address, whatever the origin of the email (mass mailing or transactional).
    Used to evaluate the configurable auto blacklist rule. """
    _name = 'mail.bounce.event'
    _description = 'Email Delivery Failure'
    _order = 'event_date desc, id desc'
    _rec_name = 'email'

    email = fields.Char('Email', required=True, index=True, readonly=True)
    event_date = fields.Datetime('Date', required=True, default=fields.Datetime.now, index=True, readonly=True)
    event_type = fields.Selection([
        ('bounce', 'Bounce'),
        ('smtp_error', 'SMTP Recipient Refused'),
    ], string='Type', required=True, readonly=True,
        help='How the failure was detected: an actual bounce (NDR) received by email, '
             'or the SMTP server refusing the recipient synchronously while sending.')
    bounce_type = fields.Selection(
        BOUNCE_TYPE_SELECTION, string='Severity', readonly=True,
        help='Best-effort classification of the failure:\n'
             '- Hard (Permanent): will not resolve on its own (bad domain, unknown user...). '
             'Retrying is pointless.\n'
             '- Soft (Temporary): may resolve on its own (full mailbox, server busy, '
             'greylisting...). Only worth blacklisting if it keeps happening.\n'
             'Guessed from the DSN Status/Action fields when present, an explicit SMTP code, '
             'or known phrases as a last resort; defaults to Soft when inconclusive.')
    reason = fields.Text('Reason', readonly=True)
    active = fields.Boolean(
        default=True,
        help='Archived failures are not counted anymore (the address was removed from the '
             'blacklist or replied to an email).')

    # ------------------------------------------------------------
    # CONFIGURATION
    # ------------------------------------------------------------

    @api.model
    def _get_auto_blacklist_config(self):
        ICP = self.env['ir.config_parameter'].sudo()

        def _int_param(key, default):
            try:
                return int(ICP.get_param(PARAM_PREFIX + key, default))
            except (TypeError, ValueError):
                return default

        return {
            'enabled': tools.str2bool(ICP.get_param(PARAM_PREFIX + 'enabled', 'False')),
            'threshold': max(_int_param('threshold', DEFAULT_THRESHOLD), 1),
            'window_days': max(_int_param('window_days', DEFAULT_WINDOW_DAYS), 0),
            'min_spread_days': max(_int_param('min_spread_days', DEFAULT_MIN_SPREAD_DAYS), 0),
            'count_smtp_errors': tools.str2bool(ICP.get_param(PARAM_PREFIX + 'count_smtp_errors', 'False')),
        }

    @api.model
    def _is_auto_blacklist_enabled(self):
        return self._get_auto_blacklist_config()['enabled']

    # ------------------------------------------------------------
    # BOUNCE TYPE CLASSIFICATION
    # ------------------------------------------------------------

    @api.model
    def _classify_bounce_type(self, text, default='soft'):
        """ Best-effort soft/hard classification of a delivery failure.

        This only feeds the ``bounce_type`` badge/filter shown in the UI; it
        does NOT affect the auto-blacklist threshold (``_check_auto_blacklist``
        counts every event the same regardless of severity).

        Tried in this order, from most to least reliable:
        1. Standard DSN fields (RFC 3464): ``Status: 5.x.x``/``4.x.x`` or
           ``Action: failed``/``delayed``.
        2. An explicit SMTP reply code (any 5xx hard, any 4xx soft, per RFC 5321).
        3. Known phrases, for bounces without any DSN/code at all (e.g. Gmail's
           own plain-text "domain not found" notice).
        Returns ``default`` when nothing conclusive is found -- callers that
        already know the failure can only be one kind (e.g. a synchronous SMTP
        recipient refusal, always permanent by definition) should pass
        ``default='hard'`` instead of relying on the generic 'soft' fallback.

        :param str text: raw bounce content (DSN fields and/or human text)
        :param str default: returned when no signal is found ('soft' or 'hard')
        :return: 'soft' or 'hard'
        """
        if not text:
            return default
        status_match = _STATUS_RE.search(text)
        if status_match:
            return 'hard' if status_match.group(1) == '5' else 'soft'
        action_match = _ACTION_RE.search(text)
        if action_match:
            action = action_match.group(1).lower()
            if action == 'failed':
                return 'hard'
            if action == 'delayed':
                return 'soft'
        if _HARD_CODE_RE.search(text):
            return 'hard'
        if _SOFT_CODE_RE.search(text):
            return 'soft'
        lowered = text.lower()
        if any(phrase in lowered for phrase in _HARD_PHRASES):
            return 'hard'
        if any(phrase in lowered for phrase in _SOFT_PHRASES):
            return 'soft'
        return default

    # ------------------------------------------------------------
    # BUSINESS
    # ------------------------------------------------------------

    @api.model
    def _register_failures(self, emails, event_type, reason=False, bounce_type=False):
        """ Log a failure for each given email and blacklist the ones reaching
        the configured threshold.

        :param emails: iterable of (not necessarily normalized) email addresses
        :param str event_type: 'bounce' or 'smtp_error'
        :param str reason: bounce message / SMTP error, stored for audit
        :param str bounce_type: 'soft'/'hard' if already known by the caller;
            guessed from ``reason`` otherwise
        :return: created <mail.bounce.event> records
        """
        config = self._get_auto_blacklist_config()
        if not config['enabled']:
            return self.browse()
        if event_type == 'smtp_error' and not config['count_smtp_errors']:
            return self.browse()
        normalized_emails = {tools.email_normalize(email) for email in emails} - {False}
        if not normalized_emails:
            return self.browse()
        bounce_type = bounce_type or self._classify_bounce_type(reason)
        events = self.sudo().create([{
            'email': email,
            'event_type': event_type,
            'reason': reason,
            'bounce_type': bounce_type,
        } for email in normalized_emails])
        self._check_auto_blacklist(normalized_emails, config)
        return events

    @api.model
    def _check_auto_blacklist(self, emails, config=None):
        """ Blacklist emails having at least ``threshold`` active failures within
        the last ``window_days`` days (0 = no time limit), the first and the last
        one being at least ``min_spread_days`` days apart (0 = no constraint). """
        config = config or self._get_auto_blacklist_config()
        emails = list(emails)
        domain = [('email', 'in', emails)]
        if config['window_days']:
            domain.append(('event_date', '>=', fields.Datetime.now() - timedelta(days=config['window_days'])))
        groups = self.sudo()._read_group(domain, ['email'], ['__count', 'event_date:min', 'event_date:max'])

        Blacklist = self.env['mail.blacklist'].sudo()
        already_blacklisted = set(Blacklist.search([('email', 'in', emails)]).mapped('email'))
        blacklisted = Blacklist
        for email, count, date_min, date_max in groups:
            if email in already_blacklisted or count < config['threshold']:
                continue
            if config['min_spread_days'] and date_max - date_min < timedelta(days=config['min_spread_days']):
                continue
            message = _(
                'This email has been automatically added to the blocklist after %(count)s delivery '
                'failures (limit: %(threshold)s, period: %(period)s).',
                count=count,
                threshold=config['threshold'],
                period=_('%s days', config['window_days']) if config['window_days'] else _('no time limit'),
            )
            blacklisted |= Blacklist.with_context(**{SKIP_NATIVE_AUTO_BLACKLIST: False})._add(
                email, message=Markup('<p>%s</p>') % message,
            )
        return blacklisted

    @api.model
    def _reset_failures(self, emails):
        """ Archive the failures of the given emails so they start counting from
        zero again (manual removal from the blacklist, reply received...). """
        normalized_emails = list({tools.email_normalize(email) for email in emails} - {False})
        if normalized_emails:
            self.sudo().search([('email', 'in', normalized_emails)]).write({'active': False})
