import email as email_module
from datetime import timedelta

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged

from odoo.addons.l10n_ve_mail_auto_blacklist.models.mail_bounce_event import (
    DEFAULT_THRESHOLD, PARAM_PREFIX, SKIP_NATIVE_AUTO_BLACKLIST,
)

SMTP_REFUSED = (
    "Mail delivery failed via SMTP server 'smtp.example.com'.\n"
    "SMTPRecipientsRefused: {'%s': (550, b'5.1.1 User unknown')}"
)


@tagged('post_install', '-at_install')
class TestAutoBlacklist(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.BounceEvent = cls.env['mail.bounce.event']
        cls.Blacklist = cls.env['mail.blacklist']
        cls.email = 'bouncing@example.com'
        cls._set_config(enabled=True, threshold=3, window_days=30, min_spread_days=0, count_smtp_errors=True)

    @classmethod
    def _set_config(cls, **values):
        ICP = cls.env['ir.config_parameter'].sudo()
        for key, value in values.items():
            ICP.set_param(PARAM_PREFIX + key, value)

    def _is_blacklisted(self, email):
        return bool(self.Blacklist.search([('email', '=', email)]))

    def _create_event(self, email, days_ago):
        return self.BounceEvent.create({
            'email': email,
            'event_type': 'bounce',
            'event_date': fields.Datetime.now() - timedelta(days=days_ago),
        })

    def _bounce_dict(self, email):
        return {
            'bounced_email': email,
            'bounced_partner': self.env['res.partner'],
            'bounced_msg_ids': [],
            'bounced_message': self.env['mail.message'],
            'body': '<p>550 5.1.1 User unknown</p>',
            'email_from': 'mailer-daemon@example.com',
            'to': self.email,
            'message_id': '<bounce@example.com>',
        }

    # ------------------------------------------------------------
    # RULE
    # ------------------------------------------------------------

    def test_threshold_within_window(self):
        self._create_event(self.email, days_ago=40)  # outside of the window: not counted
        self.BounceEvent._register_failures([self.email], 'bounce')
        self.BounceEvent._register_failures(['Bouncing <BOUNCING@example.com>'], 'bounce')
        self.assertFalse(self._is_blacklisted(self.email))
        self.BounceEvent._register_failures([self.email], 'bounce')
        self.assertTrue(self._is_blacklisted(self.email))

    def test_no_time_limit(self):
        self._set_config(window_days=0)
        self._create_event(self.email, days_ago=400)
        self._create_event(self.email, days_ago=200)
        self.BounceEvent._register_failures([self.email], 'bounce')
        self.assertTrue(self._is_blacklisted(self.email))

    def test_min_spread(self):
        self._set_config(threshold=2, min_spread_days=7)
        self._create_event(self.email, days_ago=3)
        self.BounceEvent._register_failures([self.email], 'bounce')
        self.assertFalse(self._is_blacklisted(self.email), 'Failures are too close to each other')
        self._create_event(self.email, days_ago=10)
        self.BounceEvent._register_failures([self.email], 'bounce')
        self.assertTrue(self._is_blacklisted(self.email))

    def test_disabled(self):
        self._set_config(enabled=False)
        events = self.BounceEvent._register_failures([self.email] * 5, 'bounce')
        self.assertFalse(events)
        self.assertFalse(self._is_blacklisted(self.email))

    def test_manual_removal_resets_counter(self):
        self._set_config(threshold=2)
        self.BounceEvent._register_failures([self.email], 'bounce')
        self.BounceEvent._register_failures([self.email], 'bounce')
        self.assertTrue(self._is_blacklisted(self.email))

        self.Blacklist._remove(self.email)
        self.assertFalse(self._is_blacklisted(self.email))
        self.assertFalse(self.BounceEvent.search([('email', '=', self.email)]))

        self.BounceEvent._register_failures([self.email], 'bounce')
        self.assertFalse(self._is_blacklisted(self.email), 'Counter must restart after a manual removal')

    def test_unlink_resets_counter(self):
        self._set_config(threshold=1)
        self.BounceEvent._register_failures([self.email], 'bounce')
        self.assertTrue(self._is_blacklisted(self.email))

        self.Blacklist.search([('email', '=', self.email)]).unlink()
        self.assertFalse(self.BounceEvent.search([('email', '=', self.email)]), 'Unlink must reset the counter too')

    def test_write_unrelated_field_does_not_reset_counter(self):
        self._set_config(threshold=1)
        self.BounceEvent._register_failures([self.email], 'bounce')
        record = self.Blacklist.search([('email', '=', self.email)])

        record.write({'active': True})  # no-op on 'active', must not trigger a reset
        self.assertTrue(self.BounceEvent.search([('email', '=', self.email)]))

    def test_get_blacklisted_emails_ignores_invalid_addresses(self):
        self.assertEqual(self.Blacklist._get_blacklisted_emails(['', False, 'not-an-email']), set())

    def test_invalid_config_param_falls_back_to_default(self):
        self._set_config(threshold='not-a-number')
        self.assertEqual(self.BounceEvent._get_auto_blacklist_config()['threshold'], DEFAULT_THRESHOLD)

    def test_register_failures_ignores_invalid_emails(self):
        self.assertFalse(self.BounceEvent._register_failures(['', False], 'bounce'))

    def test_reset_failures_noop_without_valid_emails(self):
        self._create_event(self.email, days_ago=0)
        self.BounceEvent._reset_failures(['', False])
        self.assertTrue(self.BounceEvent.search([('email', '=', self.email), ('active', '=', True)]),
                        'No valid email was passed, nothing should have been reset')

    # ------------------------------------------------------------
    # BOUNCES
    # ------------------------------------------------------------

    def test_routing_handle_bounce_disabled_uses_native_behavior(self):
        self._set_config(enabled=False)
        self.env['mail.thread']._routing_handle_bounce(None, self._bounce_dict(self.email))
        self.assertFalse(self.BounceEvent.search([('email', '=', self.email)]),
                          'The configurable rule must not run while disabled')

    def test_routing_handle_bounce_without_bounced_email(self):
        message_dict = self._bounce_dict(self.email)
        message_dict['bounced_email'] = False
        self.env['mail.thread']._routing_handle_bounce(None, message_dict)
        self.assertFalse(self.BounceEvent.search([]), 'Nothing to register without a bounced email')

    def test_routing_reset_bounce_restarts_counter(self):
        self._create_event(self.email, days_ago=0)
        self.env['mail.thread']._routing_reset_bounce(None, {'email_from': self.email})
        self.assertFalse(self.BounceEvent.search([('email', '=', self.email), ('active', '=', True)]),
                          'Receiving an email from the address must reset its failure counter')

    def test_native_rule_is_replaced(self):
        """ 5 bounced traces spread over 2 weeks trigger the native rule of
        mass_mailing; with a threshold of 10 nothing must be blacklisted. """
        self._set_config(threshold=10)
        partner = self.env['res.partner'].create({'name': 'Bouncing', 'email': self.email})
        traces = self.env['mailing.trace'].create([{
            'trace_type': 'mail',
            'model': 'res.partner',
            'res_id': partner.id,
            'email': self.email,
            'trace_status': 'bounce',
        } for _i in range(5)])
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE mailing_trace SET write_date = now() - interval '14 days' WHERE id = %s", (traces[0].id,))
        traces.invalidate_recordset(['write_date'])

        self.env['mail.thread']._routing_handle_bounce(None, self._bounce_dict(self.email))
        self.assertFalse(self._is_blacklisted(self.email))
        self.assertEqual(self.BounceEvent.search_count([('email', '=', self.email)]), 1)

    def test_bounce_routing_blacklists(self):
        self._set_config(threshold=2)
        self.env['mail.thread']._routing_handle_bounce(None, self._bounce_dict(self.email))
        self.env['mail.thread']._routing_handle_bounce(None, self._bounce_dict(self.email))
        self.assertTrue(self._is_blacklisted(self.email))

    def test_skip_native_context(self):
        self.Blacklist.with_context(**{SKIP_NATIVE_AUTO_BLACKLIST: True})._add(self.email)
        self.assertFalse(self._is_blacklisted(self.email))
        self.Blacklist._add(self.email)
        self.assertTrue(self._is_blacklisted(self.email), 'Manual additions are never blocked')

    # ------------------------------------------------------------
    # SMTP ERRORS
    # ------------------------------------------------------------

    def test_smtp_recipient_refused(self):
        self._set_config(threshold=1)
        mail = self.env['mail.mail'].create({'email_to': f'{self.email}, ok@example.com', 'subject': 'Test'})
        mail._postprocess_sent_message([], [], failure_reason=SMTP_REFUSED % self.email, failure_type='unknown')
        self.assertTrue(self._is_blacklisted(self.email))
        self.assertFalse(self._is_blacklisted('ok@example.com'), 'Only refused addresses are counted')

    def test_smtp_server_error_not_counted(self):
        self._set_config(threshold=1)
        mail = self.env['mail.mail'].create({'email_to': self.email, 'subject': 'Test'})
        mail._postprocess_sent_message(
            [], [], failure_reason='Connection unexpectedly closed', failure_type='mail_smtp')
        self.assertFalse(self._is_blacklisted(self.email))

    def test_smtp_errors_option(self):
        self._set_config(threshold=1, count_smtp_errors=False)
        mail = self.env['mail.mail'].create({'email_to': self.email, 'subject': 'Test'})
        mail._postprocess_sent_message([], [], failure_reason=SMTP_REFUSED % self.email, failure_type='unknown')
        self.assertFalse(self._is_blacklisted(self.email))

    def test_smtp_recipient_already_succeeded_not_counted(self):
        """ The address is quoted in a (spurious) refusal-looking reason, but it is
        also in ``success_emails``: it must not be counted as a failure. """
        self._set_config(threshold=1)
        mail = self.env['mail.mail'].create({'email_to': self.email, 'subject': 'Test'})
        mail._postprocess_sent_message(
            [], [self.email], failure_reason=SMTP_REFUSED % self.email, failure_type='unknown')
        self.assertFalse(self._is_blacklisted(self.email))

    # ------------------------------------------------------------
    # SENDING
    # ------------------------------------------------------------

    def test_block_fully_blacklisted_mail(self):
        self.Blacklist._add(self.email)
        partner = self.env['res.partner'].create({'name': 'Bouncing', 'email': self.email})
        mail = self.env['mail.mail'].create({
            'email_to': self.email,
            'recipient_ids': [(4, partner.id)],
            'subject': 'Invoice',
        })
        mail._send()
        self.assertEqual(mail.state, 'cancel')
        self.assertEqual(mail.failure_type, 'mail_bl')

    def test_strip_blacklisted_recipients(self):
        self.Blacklist._add(self.email)
        blocked_partner = self.env['res.partner'].create({'name': 'Bouncing', 'email': self.email})
        ok_partner = self.env['res.partner'].create({'name': 'Ok', 'email': 'ok@example.com'})
        mail = self.env['mail.mail'].create({
            'email_to': f'{self.email}, other@example.com',
            'recipient_ids': [(4, blocked_partner.id), (4, ok_partner.id)],
            'subject': 'Invoice',
        })
        mail._send()
        self.assertEqual(mail.state, 'outgoing', 'Mail is still sent to the other recipients')

        email_list = mail._prepare_outgoing_list()
        sent_to = {email for values in email_list for email in values['email_to_normalized']}
        self.assertEqual(sent_to, {'other@example.com', 'ok@example.com'})
        self.assertNotIn(blocked_partner, [values['partner_id'] for values in email_list])

    def test_no_block_when_disabled(self):
        self._set_config(enabled=False)
        self.Blacklist._add(self.email)
        mail = self.env['mail.mail'].create({'email_to': self.email, 'subject': 'Invoice'})
        mail._send()
        self.assertEqual(mail.state, 'outgoing')

    def test_cancel_blocked_mails_noop_without_blacklist(self):
        mail = self.env['mail.mail'].create({'email_to': 'ok@example.com', 'subject': 'Invoice', 'state': 'outgoing'})
        self.assertFalse(mail._auto_blacklist_cancel_blocked_mails())

    def test_prepare_outgoing_list_untouched_when_disabled(self):
        self._set_config(enabled=False)
        self.Blacklist._add(self.email)
        mail = self.env['mail.mail'].create({'email_to': self.email, 'subject': 'Invoice'})
        email_list = mail._prepare_outgoing_list()
        sent_to = {email for values in email_list for email in values['email_to_normalized']}
        self.assertIn(self.email, sent_to)

    def test_prepare_outgoing_list_untouched_without_blacklist(self):
        mail = self.env['mail.mail'].create({'email_to': 'ok@example.com', 'subject': 'Invoice'})
        email_list = mail._prepare_outgoing_list()
        sent_to = {email for values in email_list for email in values['email_to_normalized']}
        self.assertEqual(sent_to, {'ok@example.com'})

    def test_strip_blacklisted_recipient_without_partner(self):
        """ A blacklisted plain email address (no matching partner) must still
        be stripped, without touching ``mail.notification`` (no partner to cancel). """
        self.Blacklist._add(self.email)
        mail = self.env['mail.mail'].create({'email_to': f'{self.email}, ok@example.com', 'subject': 'Invoice'})
        email_list = mail._prepare_outgoing_list()
        sent_to = {email for values in email_list for email in values['email_to_normalized']}
        self.assertEqual(sent_to, {'ok@example.com'})

    # ------------------------------------------------------------
    # CONFIGURATION UI
    # ------------------------------------------------------------

    # ------------------------------------------------------------
    # BOUNCE TYPE CLASSIFICATION (soft/hard)
    # ------------------------------------------------------------

    def test_classify_bounce_type_from_dsn_status(self):
        self.assertEqual(self.BounceEvent._classify_bounce_type('Status: 5.1.1'), 'hard')
        self.assertEqual(self.BounceEvent._classify_bounce_type('Status: 4.2.2'), 'soft')

    def test_classify_bounce_type_from_dsn_action(self):
        self.assertEqual(self.BounceEvent._classify_bounce_type('Action: failed'), 'hard')
        self.assertEqual(self.BounceEvent._classify_bounce_type('Action: delayed'), 'soft')

    def test_classify_bounce_type_from_explicit_code(self):
        self.assertEqual(self.BounceEvent._classify_bounce_type('550 5.1.1 User unknown'), 'hard')
        self.assertEqual(self.BounceEvent._classify_bounce_type('452 4.2.2 Mailbox full'), 'soft')

    def test_classify_bounce_type_from_known_phrases(self):
        """ Some providers (Gmail included) send a bounce with no DSN block and
        no SMTP code at all when the domain does not even resolve. """
        gmail_nxdomain = (
            "Tu mensaje no se ha entregado porque no se ha encontrado el dominio example.invalid.\n"
            "DNS Error: DNS type 'mx' lookup of example.invalid responded with code NXDOMAIN"
        )
        self.assertEqual(self.BounceEvent._classify_bounce_type(gmail_nxdomain), 'hard')
        self.assertEqual(self.BounceEvent._classify_bounce_type('452 mailbox full, try again later'), 'soft')

    def test_classify_bounce_type_defaults_to_soft(self):
        self.assertEqual(self.BounceEvent._classify_bounce_type(''), 'soft')
        self.assertEqual(self.BounceEvent._classify_bounce_type(False), 'soft')
        self.assertEqual(self.BounceEvent._classify_bounce_type('no recognizable signal here'), 'soft')

    def test_classify_bounce_type_custom_default(self):
        """ Callers that already know the failure can only be one kind (e.g. a
        synchronous SMTP refusal) may override the inconclusive-case default. """
        self.assertEqual(self.BounceEvent._classify_bounce_type('no recognizable signal here', default='hard'), 'hard')
        # an explicit signal still wins over the caller's default
        self.assertEqual(self.BounceEvent._classify_bounce_type('Status: 4.2.2', default='hard'), 'soft')

    def test_classify_bounce_type_any_smtp_code(self):
        """ Per RFC 5321 any 5xx is permanent and any 4xx is temporary, not
        just the handful of codes seen in practice. """
        self.assertEqual(self.BounceEvent._classify_bounce_type('501 5.5.4 Syntax error'), 'hard')
        self.assertEqual(self.BounceEvent._classify_bounce_type('535 Authentication failed'), 'hard')
        self.assertEqual(self.BounceEvent._classify_bounce_type('432 Recipient temporarily unavailable'), 'soft')

    def test_register_failures_stores_given_bounce_type(self):
        self.BounceEvent._register_failures([self.email], 'bounce', bounce_type='hard')
        event = self.BounceEvent.search([('email', '=', self.email)])
        self.assertEqual(event.bounce_type, 'hard')

    def test_register_failures_guesses_bounce_type_from_reason(self):
        self.BounceEvent._register_failures([self.email], 'bounce', reason='Status: 5.1.1')
        event = self.BounceEvent.search([('email', '=', self.email)])
        self.assertEqual(event.bounce_type, 'hard')

    def test_smtp_recipient_refused_classified_as_hard(self):
        """ RECIPIENT_REFUSED_RE only matches 55x/5.1.x codes, so a synchronous
        SMTP refusal is always a hard failure. """
        self._set_config(threshold=1)
        mail = self.env['mail.mail'].create({'email_to': self.email, 'subject': 'Test'})
        mail._postprocess_sent_message([], [], failure_reason=SMTP_REFUSED % self.email, failure_type='unknown')
        event = self.BounceEvent.search([('email', '=', self.email)])
        self.assertEqual(event.bounce_type, 'hard')

    def test_extract_bounce_text_handles_missing_email_message(self):
        """ _routing_handle_bounce is sometimes called with email_message=None
        in tests; classification must not crash and fall back to 'soft'. """
        self._set_config(threshold=1)
        self.env['mail.thread']._routing_handle_bounce(None, self._bounce_dict(self.email))
        event = self.BounceEvent.search([('email', '=', self.email)])
        self.assertEqual(event.bounce_type, 'soft')

    def test_smtp_recipient_refused_without_code_defaults_to_hard(self):
        """ RECIPIENT_REFUSED_RE also matches the bare 'SMTPRecipientsRefused'
        string with no code attached; without a concrete 4xx/5xx signal to read,
        it must still default to 'hard' (a recipient-level refusal context),
        not fall through to the generic 'soft' default. """
        self._set_config(threshold=1)
        mail = self.env['mail.mail'].create({'email_to': self.email, 'subject': 'Test'})
        mail._postprocess_sent_message(
            [], [], failure_reason='SMTPRecipientsRefused: %s' % self.email, failure_type='unknown')
        event = self.BounceEvent.search([('email', '=', self.email)])
        self.assertEqual(event.bounce_type, 'hard')

    def _build_multi_recipient_dsn(self, status_by_recipient):
        boundary = 'TEST_BOUNDARY'
        blocks = ''.join(
            'Action: %s\nStatus: %s\nFinal-Recipient: rfc822;%s\n\n' % (
                'failed' if status.startswith('5') else 'delayed', status, recipient,
            )
            for recipient, status in status_by_recipient.items()
        )
        raw = (
            'From: Mail Delivery Subsystem <mailer-daemon@example.com>\n'
            'To: sender@example.com\n'
            'Subject: Delivery Status Notification (Mixed)\n'
            'Content-Type: multipart/report; report-type=delivery-status; boundary="%s"\n'
            '\n'
            '--%s\n'
            'Content-Type: text/plain; charset=utf-8\n'
            '\n'
            'Some recipients failed.\n'
            '\n'
            '--%s\n'
            'Content-Type: message/delivery-status\n'
            '\n'
            'Reporting-MTA: dns;mx.example.com\n'
            '\n'
            '%s'
            '--%s--\n'
        ) % (boundary, boundary, boundary, blocks, boundary)
        return email_module.message_from_bytes(raw.encode('utf-8'))

    def test_extract_bounce_text_picks_the_matching_recipient_block(self):
        """ A single DSN can carry one block per original recipient; reading
        whichever Status: appears first in the concatenated text (instead of
        the block for the recipient we are actually registering) would
        misclassify one of the two addresses below. """
        msg = self._build_multi_recipient_dsn({
            'soft-one@example.com': '4.2.2',
            'hard-two@example.com': '5.1.1',
        })
        MailThread = self.env['mail.thread']
        text_for_hard = MailThread._l10n_ve_extract_bounce_text(msg, 'hard-two@example.com')
        self.assertEqual(self.BounceEvent._classify_bounce_type(text_for_hard), 'hard')
        text_for_soft = MailThread._l10n_ve_extract_bounce_text(msg, 'soft-one@example.com')
        self.assertEqual(self.BounceEvent._classify_bounce_type(text_for_soft), 'soft')

    # ------------------------------------------------------------
    # BLACKLIST UI HELPERS
    # ------------------------------------------------------------

    def test_blacklist_bounce_info_computed_fields(self):
        self._set_config(threshold=1)
        self.BounceEvent._register_failures([self.email], 'bounce', bounce_type='hard')
        record = self.Blacklist.search([('email', '=', self.email)])
        self.assertEqual(record.l10n_ve_bounce_event_count, 1)
        self.assertEqual(record.l10n_ve_last_bounce_type, 'hard')

    def test_blacklist_bounce_info_without_events(self):
        self.Blacklist._add(self.email)
        record = self.Blacklist.search([('email', '=', self.email)])
        self.assertEqual(record.l10n_ve_bounce_event_count, 0)
        self.assertFalse(record.l10n_ve_last_bounce_type)

    def test_action_view_bounce_events_domain(self):
        self._set_config(threshold=1)
        self.BounceEvent._register_failures([self.email], 'bounce')
        record = self.Blacklist.search([('email', '=', self.email)])
        action = record.action_l10n_ve_view_bounce_events()
        self.assertEqual(action['domain'], [('email', '=', self.email)])

    def test_action_view_bounce_events_merges_context(self):
        """ The action's own context (search_default_group_by_email=1, set on
        the <ir.actions.act_window> record) must survive alongside the
        override, not get wiped by a full reassignment. """
        self._set_config(threshold=1)
        self.BounceEvent._register_failures([self.email], 'bounce')
        record = self.Blacklist.search([('email', '=', self.email)])
        base_action = self.env.ref('l10n_ve_mail_auto_blacklist.mail_bounce_event_action')
        self.assertIn('search_default_group_by_email', base_action.context)
        action = record.action_l10n_ve_view_bounce_events()
        self.assertEqual(action['context'].get('search_default_group_by_email'), 0)

    def test_blacklist_bounce_info_does_not_mix_up_emails(self):
        """ The batched compute (one query for all records, not one per email)
        must still attribute the right count/type to the right record. """
        self._set_config(threshold=1)
        other_email = 'other-bouncing@example.com'
        self.BounceEvent._register_failures([self.email], 'bounce', bounce_type='soft')
        self.BounceEvent._register_failures([self.email], 'bounce', bounce_type='hard')
        self.BounceEvent._register_failures([other_email], 'bounce', bounce_type='soft')

        record = self.Blacklist.search([('email', '=', self.email)])
        other_record = self.Blacklist.search([('email', '=', other_email)])
        self.assertEqual(record.l10n_ve_bounce_event_count, 2)
        self.assertEqual(record.l10n_ve_last_bounce_type, 'hard')
        self.assertEqual(other_record.l10n_ve_bounce_event_count, 1)
        self.assertEqual(other_record.l10n_ve_last_bounce_type, 'soft')

    def test_config_settings_constraints(self):
        Settings = self.env['res.config.settings']
        with self.assertRaises(ValidationError):
            Settings.create({
                'l10n_ve_auto_blacklist_enabled': True,
                'l10n_ve_auto_blacklist_threshold': 0,
            }).flush_recordset()
        with self.assertRaises(ValidationError):
            Settings.create({
                'l10n_ve_auto_blacklist_enabled': True,
                'l10n_ve_auto_blacklist_threshold': 1,
                'l10n_ve_auto_blacklist_window_days': -1,
            }).flush_recordset()
        with self.assertRaises(ValidationError):
            Settings.create({
                'l10n_ve_auto_blacklist_enabled': True,
                'l10n_ve_auto_blacklist_threshold': 1,
                'l10n_ve_auto_blacklist_window_days': 7,
                'l10n_ve_auto_blacklist_min_spread_days': 7,
            }).flush_recordset()
        # a coherent configuration does not raise
        Settings.create({
            'l10n_ve_auto_blacklist_enabled': True,
            'l10n_ve_auto_blacklist_threshold': 3,
            'l10n_ve_auto_blacklist_window_days': 30,
            'l10n_ve_auto_blacklist_min_spread_days': 1,
        }).flush_recordset()
