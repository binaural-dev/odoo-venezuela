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

    def test_writing_empty_account_on_bank_line_raises(self):
        """_check_payment_account_id_required_for_bank (account_payment_method_line.py,
        code review follow-up to PR #1344 / task 81735) fires on a direct
        write to the line itself. Needed because account.journal's own
        _check_payment_method_line_accounts is a constrains on the o2m
        fields inbound/outbound_payment_method_line_ids, which Odoo does
        NOT re-evaluate from a write on the child line directly (confirmed
        via code review) -- only account_payment_method_line.py's own
        constrains closes that path."""
        self._get_foreign_bank_journal(self.currency_usd)

        with self.assertRaisesRegex(UserError, "must have an assigned account"):
            self.pm_line_in.payment_account_id = False

    def test_cash_journal_lines_without_account_do_not_raise(self):
        """The constrains (and the create() fill) are scoped to type ==
        'bank' only -- a cash journal's native lines are left exactly as
        core creates them (no account), same as before this change."""
        cash_journal = self.env["account.journal"].sudo().create({
            "name": "Caja Chica Test",
            "code": "CSHT",
            "type": "cash",
            "company_id": self.company.id,
        })
        all_lines = cash_journal.inbound_payment_method_line_ids | cash_journal.outbound_payment_method_line_ids
        self.assertTrue(all_lines)
        self.assertTrue(
            all(not line.payment_account_id for line in all_lines),
            "Cash journal lines must not be affected by the bank-only account requirement.",
        )

    def test_confirming_legacy_bank_line_without_account_raises_in_community(self):
        """Regression for the gap found in code review (PR #1344 / task
        81735): with the full Accounting app not installed (confirmed via
        dependency analysis that this test environment's accounting_installed
        is False), core's account.payment.create() falls back to
        company.transfer_account_id when outstanding_account_id is empty --
        silently using a GENERIC account instead of the one configured on
        the payment method line, or raising. _get_outstanding_account's
        override (account_payment.py) must disable that fallback for a bank
        journal whose line lacks an account, and action_post() must then
        refuse to confirm rather than let the payment through with no
        journal entry.

        The company is given a transfer_account_id FIRST, so an unpatched
        core would have silently succeeded here -- proving the block is
        ours, not an accident of a fixture company with no chart of
        accounts (the mistake in the original version of this test, found
        in code review)."""
        journal = self._get_foreign_bank_journal(self.currency_usd)
        self.company.transfer_account_id = self.account_bank

        # Simulate a pre-existing line that bypassed the ORM (legacy data
        # from before this module's fix, or any write that predates the
        # constrains added in account_payment_method_line.py) -- that
        # constrains would otherwise block this at write time, which is
        # correct going forward but not what this test exercises.
        self.env.cr.execute(
            "UPDATE account_payment_method_line SET payment_account_id = NULL WHERE id = %s",
            (self.pm_line_in.id,),
        )
        self.pm_line_in.invalidate_recordset(['payment_account_id'])

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
        self.assertFalse(
            payment.outstanding_account_id,
            "The fallback to transfer_account_id must be disabled for a bank "
            "journal whose payment method line has no account.",
        )
        with self.assertRaisesRegex(UserError, "has no account"):
            payment.action_post()

    def test_outstanding_account_override_does_not_affect_non_pos_payments_without_pos_installed(self):
        """Regression guard for a bug found in code review (PR #1344 / task
        81735, Christopher's automated review): the _get_outstanding_account
        override and the action_post() guard both exempt POS payments via
        _is_pos_payment() (pos_session_id), since pos.payment.method.outstanding_account_id
        is only ever filled by its own onchange and pos_session.py calls
        _get_outstanding_account() directly when that's empty -- without the
        exemption, closing a POS session could break for a bank journal whose
        payment method line lacks an account.

        point_of_sale is NOT a transitive dependency of l10n_ve_accountant
        (confirmed), so this module's own CI never installs it and a real
        POS-session regression test can't live here. This only confirms
        _is_pos_payment() degrades safely (returns False, doesn't raise) when
        the pos_session_id field doesn't exist at all -- the common case for
        this module's test environment -- so the exemption check itself
        never breaks a database without point_of_sale installed."""
        payment = self.env["account.payment"].create({
            "amount": 50.0,
            "date": self.payment_date,
            "currency_id": self.currency_usd.id,
            "payment_type": "inbound",
            "partner_type": "customer",
            "partner_id": self.partner.id,
            "journal_id": self._get_foreign_bank_journal(self.currency_usd).id,
            "payment_method_id": self.manual_in.id,
        })
        self.assertNotIn('pos_session_id', payment._fields)
        self.assertFalse(payment._is_pos_payment())

    def _create_valid_bank_journal(self, code):
        return self.env["account.journal"].sudo().create({
            "name": f"Bank Constrains Test {code}",
            "code": code,
            "type": "bank",
            "company_id": self.company.id,
            "default_account_id": self.account_bank.id,
        })

    def test_editing_default_account_id_does_not_unlink_extra_payment_method_lines(self):
        """Regression for pastor-binaural's finding (PR #1344 / task 81735):
        editing default_account_id on an already-saved bank journal must not
        re-trigger the native _compute_inbound/outbound_payment_method_line_ids
        (Command.clear() + recreate-defaults-only), which would unlink/delete
        any extra manual payment method line the user added -- and orphan any
        account.payment already using it."""
        journal = self.env["account.journal"].sudo().create({
            "name": "Bank Edit Account Test",
            "code": "BKEDT",
            "type": "bank",
            "company_id": self.company.id,
            "default_account_id": self.account_bank.id,
        })

        extra_method = self.env.ref("account.account_payment_method_manual_in")
        extra_line = self.env["account.payment.method.line"].with_context(
            default_journal_id=journal.id,
        ).create({
            "name": "Transferencia Bancaria",
            "payment_method_id": extra_method.id,
            "payment_type": "inbound",
            "journal_id": journal.id,
            "payment_account_id": self.account_bank.id,
        })

        other_account = self.env["account.account"].create({
            "name": "Second Bank Account",
            "code": "100200",
            "account_type": "asset_cash",
            "company_ids": [(6, 0, [self.company.id])],
            "reconcile": True,
        })

        journal.write({"default_account_id": other_account.id})

        self.assertTrue(
            extra_line.exists() and extra_line.journal_id == journal,
            "Editing default_account_id must not unlink/delete extra payment "
            "method lines added manually to the journal.",
        )
        self.assertIn(extra_line, journal.inbound_payment_method_line_ids)
        self.assertEqual(extra_line.name, "Transferencia Bancaria")

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

    def test_bank_journal_with_one_line_missing_account_raises_user_error(self):
        """Regression for _check_payment_method_line_accounts: a mix of one
        line with an account and one without must still raise, since the
        check must fail if ANY line lacks an account, not only when ALL of
        them do."""
        journal = self._create_valid_bank_journal("BKMIX")
        outbound_ids = journal.outbound_payment_method_line_ids.ids
        self.assertTrue(journal.inbound_payment_method_line_ids)
        self.assertTrue(outbound_ids)

        with self.assertRaises(UserError):
            journal.write({
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
        # Writing False directly on the line is now blocked by
        # _check_payment_account_id_required_for_bank (account_payment_method_line.py,
        # code review follow-up to PR #1344 / task 81735) -- simulate a
        # pre-existing inconsistent line (legacy data) via raw SQL instead,
        # bypassing that constrains, same as
        # test_confirming_legacy_bank_line_without_account_raises_in_community.
        outbound_line = journal.outbound_payment_method_line_ids
        self.env.cr.execute(
            "UPDATE account_payment_method_line SET payment_account_id = NULL WHERE id = %s",
            (outbound_line.id,),
        )
        outbound_line.invalidate_recordset(['payment_account_id'])

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
        # See the matching comment in
        # test_outbound_payment_excludes_journal_without_outbound_account:
        # writing False directly is now blocked by the constrains added in
        # account_payment_method_line.py, so simulate it via raw SQL.
        inbound_line = journal.inbound_payment_method_line_ids
        self.env.cr.execute(
            "UPDATE account_payment_method_line SET payment_account_id = NULL WHERE id = %s",
            (inbound_line.id,),
        )
        inbound_line.invalidate_recordset(['payment_account_id'])

        payment = self.env["account.payment"].new({
            "payment_type": "inbound",
        })

        self.assertNotIn(
            journal, payment.available_journal_ids,
            "A bank journal without an inbound payment_account_id must be "
            "excluded from available_journal_ids for inbound payments.",
        )
