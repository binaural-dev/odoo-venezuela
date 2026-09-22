import logging

from odoo.tests import tagged
from odoo.exceptions import UserError
from odoo import Command

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

    def test_bank_journal_without_default_account_raises_user_error(self):
        # Odoo's own create() (_fill_missing_values -> _create_default_account)
        # auto-generates a placeholder liquidity account whenever default_account_id
        # is missing on a bank/cash journal, so it never actually reaches our
        # constrains empty. skip_default_account_autofill disables only that
        # auto-creation so the constrains can be exercised against a genuinely
        # empty default_account_id.
        with self.assertRaises(UserError):
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

    def _create_valid_bank_journal(self, code):
        return self.env["account.journal"].sudo().create({
            "name": f"Bank Constrains Test {code}",
            "code": code,
            "type": "bank",
            "company_id": self.company.id,
            "default_account_id": self.account_bank.id,
        })

    def test_bank_journal_without_inbound_lines_raises_user_error(self):
        journal = self._create_valid_bank_journal("BKIN0")

        with self.assertRaises(UserError):
            journal.write({"inbound_payment_method_line_ids": [Command.clear()]})

    def test_bank_journal_without_outbound_lines_raises_user_error(self):
        journal = self._create_valid_bank_journal("BKOU0")

        with self.assertRaises(UserError):
            journal.write({"outbound_payment_method_line_ids": [Command.clear()]})

    def test_bank_journal_with_lines_but_no_account_raises_user_error(self):
        """Both collections keep at least one line each (only payment_account_id
        is cleared via Command.update on the existing line ids), so this
        isolates the "no line has an account" branch from the "missing
        inbound/outbound lines" branches above."""
        journal = self._create_valid_bank_journal("BKNAC")
        inbound_ids = journal.inbound_payment_method_line_ids.ids
        outbound_ids = journal.outbound_payment_method_line_ids.ids
        self.assertTrue(inbound_ids)
        self.assertTrue(outbound_ids)

        with self.assertRaises(UserError):
            journal.write({
                "inbound_payment_method_line_ids": [
                    Command.update(line_id, {"payment_account_id": False}) for line_id in inbound_ids
                ],
                "outbound_payment_method_line_ids": [
                    Command.update(line_id, {"payment_account_id": False}) for line_id in outbound_ids
                ],
            })

    def _create_support_less_user(self):
        return self.env["res.users"].create({
            "name": "No Support User",
            "login": "no_support_user_l10n_ve_accountant",
            "email": "no_support_user_l10n_ve_accountant@example.com",
            "group_ids": [Command.set([self.env.ref("base.group_user").id])],
        })

    def test_create_journal_with_prohibited_type_without_support_group_raises(self):
        other_user = self._create_support_less_user()

        with self.assertRaises(UserError):
            self.env["account.journal"].with_user(other_user).create({
                "name": "Sale Journal No Perm",
                "code": "SLNPM",
                "type": "sale",
                "company_id": self.company.id,
            })

    def test_write_journal_type_to_prohibited_type_without_support_group_raises(self):
        other_user = self._create_support_less_user()
        journal = self.env["account.journal"].sudo().create({
            "name": "Cash Journal No Perm",
            "code": "CSNPM",
            "type": "cash",
            "company_id": self.company.id,
            "default_account_id": self.account_bank.id,
        })

        with self.assertRaises(UserError):
            journal.with_user(other_user).write({"type": "sale"})

    def test_write_journal_type_to_allowed_type_without_support_group_does_not_raise(self):
        """_validate_support_user_group: a user without the support group must
        still be allowed to write an allowed type (bank/general/cash) -- the
        UserError only fires for types outside that list.

        Needs account.group_account_manager for the base ACL write access on
        account.journal (separate from l10n_ve_accountant's own support
        group, which this test deliberately withholds).
        """
        other_user = self._create_support_less_user()
        other_user.group_ids = [Command.link(self.env.ref("account.group_account_manager").id)]
        journal = self.env["account.journal"].sudo().create({
            "name": "General Journal No Perm",
            "code": "GNNPM",
            "type": "general",
            "company_id": self.company.id,
        })

        journal.with_user(other_user).write({"type": "cash"})

        self.assertEqual(journal.type, "cash")

    def test_payment_method_line_on_non_bank_journal_has_no_default_account(self):
        """_default_payment_account_id must fall back to False for any
        journal that is not of type 'bank' (e.g. 'cash')."""
        journal = self.env["account.journal"].sudo().create({
            "name": "Cash Journal Default Account Test",
            "code": "CSDEF",
            "type": "cash",
            "company_id": self.company.id,
            "default_account_id": self.account_bank.id,
        })

        extra_method = self.env.ref("account.account_payment_method_manual_in")
        new_line = self.env["account.payment.method.line"].with_context(
            default_journal_id=journal.id,
        ).create({
            "name": "Cash Manual Inbound",
            "payment_method_id": extra_method.id,
            "payment_type": "inbound",
            "journal_id": journal.id,
        })

        self.assertFalse(
            new_line.payment_account_id,
            "A payment method line for a non-bank journal must not default "
            "payment_account_id to anything.",
        )

    def test_outbound_payment_excludes_journal_without_outbound_account(self):
        """_compute_available_journal_ids (outbound branch): a bank journal
        whose outbound payment method line has no payment_account_id must be
        excluded from available_journal_ids on an outbound payment."""
        journal = self._get_foreign_bank_journal(self.currency_eur)
        # Writing directly on the line (not on the journal's o2m field) does
        # not re-trigger the journal's own _check_payment_method_line_accounts
        # constrains, so this leaves the journal itself in a persistable
        # (if inconsistent) state for the purpose of this test.
        outbound_line = journal.outbound_payment_method_line_ids
        outbound_line.payment_account_id = False

        payment = self.env["account.payment"].new({
            "payment_type": "outbound",
        })

        self.assertNotIn(
            journal, payment.available_journal_ids,
            "A bank journal without an outbound payment_account_id must be "
            "excluded from available_journal_ids for outbound payments.",
        )

    def test_inbound_payment_excludes_journal_without_inbound_account(self):
        """_compute_available_journal_ids (inbound branch): a bank journal
        whose inbound payment method line has no payment_account_id must be
        excluded from available_journal_ids on an inbound payment."""
        journal = self._get_foreign_bank_journal(self.currency_eur)
        inbound_line = journal.inbound_payment_method_line_ids
        inbound_line.payment_account_id = False

        payment = self.env["account.payment"].new({
            "payment_type": "inbound",
        })

        self.assertNotIn(
            journal, payment.available_journal_ids,
            "A bank journal without an inbound payment_account_id must be "
            "excluded from available_journal_ids for inbound payments.",
        )
