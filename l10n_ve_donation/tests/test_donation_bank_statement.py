import re
from datetime import timedelta

from odoo import Command, fields
from odoo.tests import tagged

from .common import TestDonationCommon


@tagged("l10n_ve_donation", "received_donation", "-at_install", "post_install")
class TestDonationFromBankStatement(TestDonationCommon):
    """A donation in money that arrives through the bank extract: the entry
    of the statement line, reconciled against a received donations account,
    is a donation received without restoring it to draft to mark it.

    Covers: REQ-DON-031.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        company_ids = [Command.set([cls.company.id])]
        cls.company.donation_income_account_ids = cls.account_income
        cls.donor = cls.env["res.partner"].create({"name": "Donor Bank Test"})
        cls.account_bank = cls.env["account.account"].create({
            "name": "Bank Test", "code": "DON111001", "account_type": "asset_cash",
            "company_ids": company_ids,
        })
        cls.account_suspense = cls.env["account.account"].create({
            "name": "Suspense Test", "code": "DON119001", "account_type": "asset_current",
            "company_ids": company_ids,
        })
        cls.journal_bank = cls.env["account.journal"].create({
            "name": "Bank Journal Test", "type": "bank", "code": "TBK",
            "company_id": cls.company.id,
            "default_account_id": cls.account_bank.id,
            "suspense_account_id": cls.account_suspense.id,
        })

    def _statement_line(self, amount=1000.0, partner=True, date=None):
        return self.env["account.bank.statement.line"].create({
            "journal_id": self.journal_bank.id,
            "date": date or fields.Date.today(),
            "payment_ref": "Gift of the donor",
            "partner_id": self.donor.id if partner else False,
            "amount": amount,
        })

    def _reconcile_against(self, statement_line, account):
        _liquidity, suspense, _other = statement_line._seek_for_lines()
        suspense.with_context(skip_readonly_check=True).write({"account_id": account.id})

    def test_01_the_reconciled_entry_is_a_donation_received(self):
        statement_line = self._statement_line()
        move = statement_line.move_id
        self.assertFalse(move.is_donation)
        self._reconcile_against(statement_line, self.account_income)
        self.assertEqual(move.state, "posted")
        self.assertTrue(move.is_donation)
        self.assertTrue(move.is_incoming_donation)
        self.assertEqual(move._get_donation_counterparty(), self.donor)
        self.assertIsInstance(move.print_donation_certificate(), dict)

    def test_02_an_entry_that_is_not_reconciled_against_a_donations_account_is_not_marked(self):
        statement_line = self._statement_line()
        self._reconcile_against(statement_line, self.account_expense)
        self.assertFalse(statement_line.move_id.is_donation)

    def test_03_a_manual_entry_is_not_marked_by_its_accounts(self):
        """Only the entries that come from the extract are marked by the
        account: the manual entry is marked by whoever registers it."""
        move = self.env["account.move"].create({
            "move_type": "entry",
            "journal_id": self.journal_bank.id,
            "line_ids": [
                Command.create({"account_id": self.account_bank.id, "debit": 100, "credit": 0}),
                Command.create({"account_id": self.account_income.id, "debit": 0, "credit": 100}),
            ],
        })
        self.assertFalse(move.is_donation)

    def test_04_without_received_donations_accounts_nothing_is_marked(self):
        self.company.donation_income_account_ids = False
        statement_line = self._statement_line()
        self._reconcile_against(statement_line, self.account_income)
        self.assertFalse(statement_line.move_id.is_donation)

    def test_05_undoing_the_reconciliation_removes_the_mark(self):
        """The mark that was set by the account is removed when the entry
        stops being a donation received: undoing the reconciliation rewrites
        the lines of the entry, which used to fail the check of the contact
        of the lines of a donation."""
        statement_line = self._statement_line()
        move = statement_line.move_id
        self._reconcile_against(statement_line, self.account_income)
        self.assertTrue(move.is_donation)
        statement_line.action_undo_reconciliation()
        self.assertFalse(move.is_donation)
        self.assertFalse(move.donation_marked_from_statement)
        # It can be reconciled again.
        self._reconcile_against(statement_line, self.account_income)
        self.assertTrue(move.is_donation)

    def test_06_changing_the_account_removes_the_mark(self):
        statement_line = self._statement_line()
        move = statement_line.move_id
        self._reconcile_against(statement_line, self.account_income)
        self.assertTrue(move.is_donation)
        income_line = move.line_ids.filtered(lambda line: line.account_id == self.account_income)
        income_line.with_context(skip_readonly_check=True).write({"account_id": self.account_expense.id})
        self.assertFalse(move.is_donation)
        self.assertFalse(move.is_incoming_donation)

    def test_07_a_payment_to_the_donor_is_not_a_donation_received(self):
        """A debit to the income account (a refund to the donor) is not a
        donation received: it would offer a certificate."""
        statement_line = self._statement_line(amount=-1000.0)
        self._reconcile_against(statement_line, self.account_income)
        self.assertFalse(statement_line.move_id.is_donation)

    def test_08_a_statement_line_without_contact_is_reconciled(self):
        """The donor is not required to reconcile: the certificate leaves it
        blank."""
        statement_line = self._statement_line(partner=False)
        self._reconcile_against(statement_line, self.account_income)
        move = statement_line.move_id
        self.assertTrue(move.is_incoming_donation)
        self.assertFalse(move._get_donation_counterparty())
        self.assertIsInstance(move.print_donation_certificate(), dict)

    def test_09_a_mark_set_by_a_person_is_not_removed(self):
        statement_line = self._statement_line()
        move = statement_line.move_id
        self._reconcile_against(statement_line, self.account_expense)
        move.is_donation = True
        self.assertFalse(move.donation_marked_from_statement)
        income = statement_line._seek_for_lines()[1]
        income.with_context(skip_readonly_check=True).write({"account_id": self.account_income.id})
        income.with_context(skip_readonly_check=True).write({"account_id": self.account_expense.id})
        self.assertTrue(move.is_donation)

    def test_10_the_certificate_of_a_line_of_a_previous_day_prints_its_date(self):
        # REQ-DON-031
        """The line of the extract is from yesterday and it is reconciled
        today: the entry keeps the date of the line (`date`, the one of its
        rate) and the certificate has to say that day, with the rate of that
        day. It printed `invoice_date` (the day it was reconciled) next to the
        rate of the day of the line."""
        today = fields.Date.today()
        yesterday = today - timedelta(days=1)
        self.env["res.currency.rate"].create({
            "currency_id": self.env.ref("base.USD").id,
            "company_id": self.company.id,
            "name": yesterday,
            "rate": 1.0 / 400.0,
        })
        statement_line = self._statement_line(date=yesterday)
        move = statement_line.move_id
        self._reconcile_against(statement_line, self.account_income)
        # The entry keeps the date of the line, and the day it was reconciled
        # (today) is the one that `invoice_date` carries.
        self.assertEqual(move.date, yesterday)
        self.assertEqual(move.invoice_date, today)
        self.assertEqual(move._get_donation_amounts()["rate"], 400.0)

        report = self.env.ref("l10n_ve_donation.action_donation_certificate_account_move")
        html, _report_type = report._render_qweb_html(report.report_name, move.ids)
        text = " ".join(re.sub(r"<[^>]+>", " ", html.decode()).split())
        self.assertIn(f"rate of the day {yesterday.strftime('%d/%m/%Y')}", text)
        self.assertNotIn(today.strftime("%d/%m/%Y"), text)
