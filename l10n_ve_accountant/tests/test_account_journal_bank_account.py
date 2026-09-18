import logging

from odoo.tests import tagged
from odoo.exceptions import UserError, ValidationError

from .test_indexed_payments import TestIndexedPayments

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "l10n_ve_accountant_journal_bank_account")
class TestAccountJournalBankAccount(TestIndexedPayments):
    """
    Validates that a bank journal's default_account_id (Cuenta Bancaria) is
    propagated to its payment method lines' payment_account_id even when
    created in a single API call (no onchange involved), that default_account_id
    is mandatory for bank journals, and that the resulting payment method
    lines never fall back to a silently-picked account when they lack one.

    Reuses TestIndexedPayments' setUp (company VEF/USD/EUR, rates, accounts,
    partner, product, tax) instead of rebuilding fixtures.
    """

    def test_create_bank_journal_with_default_account_fills_payment_method_lines(self):
        journal = self.env["account.journal"].sudo().create({
            "name": "Bank Create Test",
            "code": "BKCRT",
            "type": "bank",
            "company_id": self.company.id,
            "default_account_id": self.account_bank.id,
        })

        all_lines = journal.inbound_payment_method_line_ids | journal.outbound_payment_method_line_ids
        self.assertTrue(all_lines)
        for line in all_lines:
            self.assertEqual(
                line.payment_account_id, self.account_bank,
                "Every payment method line auto-generated on create must take the "
                "journal's default_account_id, even without going through any onchange.",
            )

    def test_bank_journal_without_default_account_raises_validation_error(self):
        # Odoo's own create() (_fill_missing_values -> _create_default_account)
        # auto-generates a placeholder liquidity account whenever default_account_id
        # is missing on a bank/cash journal, so it never actually reaches our
        # constrains empty. skip_default_account_autofill disables only that
        # auto-creation so the constrains can be exercised against a genuinely
        # empty default_account_id.
        with self.assertRaises(ValidationError):
            self.env["account.journal"].sudo().with_context(
                skip_default_account_autofill=True,
            ).create({
                "name": "Bank No Account Test",
                "code": "BKNOA",
                "type": "bank",
                "company_id": self.company.id,
            })

    def test_manual_payment_method_line_defaults_to_journal_account(self):
        journal = self.env["account.journal"].sudo().create({
            "name": "Bank Manual Line Test",
            "code": "BKMAN",
            "type": "bank",
            "company_id": self.company.id,
            "default_account_id": self.account_bank.id,
        })

        extra_method = self.env.ref("account.account_payment_method_manual_in")
        new_line = self.env["account.payment.method.line"].with_context(
            default_journal_id=journal.id,
        ).create({
            "name": "Extra Manual Inbound",
            "payment_method_id": extra_method.id,
            "payment_type": "inbound",
            "journal_id": journal.id,
        })

        self.assertEqual(
            new_line.payment_account_id, self.account_bank,
            "A payment method line created manually for a bank journal must "
            "default payment_account_id to the journal's default_account_id.",
        )

    def test_payment_with_configured_account_creates_move(self):
        journal = self._get_foreign_bank_journal(self.currency_usd)
        payment = self.env["account.payment"].create({
            "amount": 50.0,
            "date": self.payment_date,
            "currency_id": self.currency_usd.id,
            "payment_type": "inbound",
            "partner_type": "customer",
            "partner_id": self.partner.id,
            "journal_id": journal.id,
            "payment_method_id": self.manual_in.id,
        })
        payment.action_post()
        self.assertTrue(payment.move_id, "A correctly configured journal must produce a move on posting.")

    def test_payment_method_line_without_account_never_falls_back_silently(self):
        """Regression guard: even if a payment method line ends up without a
        payment_account_id (bypassing the journal-level safeguards on purpose,
        as done here via a direct write), Odoo must refuse to post the
        payment rather than silently picking some other account.

        _check_payment_method_line_accounts (pre-existing, not touched here)
        already blocks this at the journal level before a payment can even be
        attempted with such a line, so this test exercises that same
        guarantee rather than reimplementing it -- there's no separate code
        path in core Odoo to bypass account_id determination once the line
        exists without one."""
        journal = self._get_foreign_bank_journal(self.currency_usd)
        self.pm_line_in.payment_account_id = False

        with self.assertRaises(UserError):
            self.env["account.payment"].create({
                "amount": 50.0,
                "date": self.payment_date,
                "currency_id": self.currency_usd.id,
                "payment_type": "inbound",
                "partner_type": "customer",
                "partner_id": self.partner.id,
                "journal_id": journal.id,
                "payment_method_id": self.manual_in.id,
            })
