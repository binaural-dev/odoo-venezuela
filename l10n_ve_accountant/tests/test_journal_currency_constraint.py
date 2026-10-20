import logging

from odoo.tests import tagged
from odoo import Command
from odoo.exceptions import UserError

from .test_indexed_payments import TestIndexedPayments

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "l10n_ve_accountant_journal_currency")
class TestJournalCurrencyConstraint(TestIndexedPayments):
    """
    Validates the journal-currency guard added to
    AccountMoveLine._check_constrains_account_id_journal_id: a journal with a
    forced currency must reject entries in any other currency, while a
    journal with no currency accepts any.

    Reuses TestIndexedPayments' setUp (company VEF/USD/EUR, rates, accounts,
    partner, product, tax) instead of rebuilding fixtures.
    """

    def _create_move(self, journal, currency):
        return self.env["account.move"].create({
            "move_type": "entry",
            "journal_id": journal.id,
            "date": self.invoice_date,
            "line_ids": [
                Command.create({
                    "account_id": self.account_income.id,
                    "currency_id": currency.id,
                    "debit": 100.0,
                    "credit": 0.0,
                    "amount_currency": 100.0,
                }),
                Command.create({
                    "account_id": self.account_bank.id,
                    "currency_id": currency.id,
                    "debit": 0.0,
                    "credit": 100.0,
                    "amount_currency": -100.0,
                }),
            ],
        })

    def test_journal_with_currency_rejects_mismatched_line_currency(self):
        # Plain try/except instead of assertRaises: the latter wraps the call
        # in an extra cr.savepoint(), whose eager flush can trigger this fresh
        # test company's lazy chart-template load at an unlucky moment,
        # tripping an unrelated pre-existing multi-record bug in
        # product_template._enforce_single_tax_vals. Not what this test
        # covers -- avoid it instead of chasing it here.
        usd_journal = self._get_foreign_bank_journal(self.currency_usd)
        move = self._create_move(usd_journal, self.currency_vef)
        try:
            move.action_post()
            self.fail("Expected a UserError for a VEF-denominated entry in a USD-only journal.")
        except UserError:
            pass

    def test_journal_with_currency_accepts_matching_line_currency(self):
        usd_journal = self._get_foreign_bank_journal(self.currency_usd)
        move = self._create_move(usd_journal, self.currency_usd)
        move.action_post()
        self.assertEqual(move.state, "posted")

    def test_journal_without_currency_accepts_any_line_currency(self):
        journal_no_currency = self.env["account.journal"].sudo().create({
            "name": "Misc Journal No Currency",
            "type": "general",
            "code": "MISCNC",
            "company_id": self.company.id,
            "currency_id": False,
            "default_account_id": self.account_income.id,
        })
        move = self._create_move(journal_no_currency, self.currency_usd)
        move.action_post()
        self.assertEqual(move.state, "posted")
