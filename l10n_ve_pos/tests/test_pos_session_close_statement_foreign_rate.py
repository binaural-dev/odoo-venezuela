"""Ticket #15169: the cash statement booked by the session closing must keep
the alternate-currency double entry when the BCV rate changed between the
sale and the closing.

``set_foreign_amount_in_line`` stamps the sale-time ``foreign_amount`` on the
POS receivable leg of the statement and mirrors it onto the cash leg. The cash
leg must be locked too (``not_foreign_recalculate``); otherwise
``l10n_ve_accountant`` recomputes it at the rate of the move date (the closing
day) and the statement ends up with foreign debit != foreign credit.
"""

from odoo import fields
from odoo.tests import tagged

from .test_pos_session_accounting_common import TestPosSessionAccountingBase


@tagged("post_install", "-at_install", "l10n_ve_pos", "pos_close_statement_foreign_rate")
class TestPosSessionCloseStatementForeignRate(TestPosSessionAccountingBase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.session = cls.env["pos.session"].create(
            {
                "config_id": cls.config.id,
                "user_id": cls.env.ref("base.user_admin").id,
            }
        )
        cls.misc_journal = cls.env["account.journal"].create(
            {
                "name": "C Misc Journal",
                "type": "general",
                "code": "MSCC",
                "company_id": cls.company.id,
            }
        )
        # Like the POS cash journals in production: no currency of its own,
        # so the statement is booked in the company currency.
        cls.company_cash_journal = cls.env["account.journal"].create(
            {
                "name": "C Company Cash",
                "type": "cash",
                "code": "CCSH",
                "company_id": cls.company.id,
                "default_account_id": cls.account_cash.id,
            }
        )
        # Closing-day rate, different from the one the sale was valued at.
        cls.env["res.currency.rate"].create(
            {
                "name": fields.Date.today(),
                "currency_id": cls.foreign_currency.id,
                "company_id": cls.company.id,
                "rate": 40.0,
            }
        )

    def _recompute_foreign(self, lines):
        lines._compute_foreign_debit_credit()
        lines.flush_recordset()

    def test_statement_cash_leg_keeps_sale_foreign_amount(self):
        statement_line = (
            self.env["account.bank.statement.line"]
            .with_company(self.company)
            .create(
                {
                    "journal_id": self.company_cash_journal.id,
                    "date": fields.Date.today(),
                    "payment_ref": self.session.name,
                    "amount": 100.0,
                    "counterpart_account_id": self.account_pos_receivable.id,
                }
            )
        )
        move_lines = statement_line.move_id.line_ids
        receivable_line = move_lines.filtered(
            lambda l: l.account_id.account_type == "asset_receivable"
        )
        cash_line = move_lines - receivable_line
        # Sale valued at 36.5 while the closing day is at 40.0.
        sale_foreign_amount = 3650.0

        self.session.set_foreign_amount_in_line(receivable_line, sale_foreign_amount, 100.0)
        self._recompute_foreign(move_lines)

        self.assertTrue(cash_line.not_foreign_recalculate)
        self.assertEqual(receivable_line.foreign_credit, sale_foreign_amount)
        self.assertEqual(cash_line.foreign_debit, sale_foreign_amount)
        self.assertEqual(
            sum(move_lines.mapped("foreign_debit")),
            sum(move_lines.mapped("foreign_credit")),
            "the cash statement must balance in the alternate currency",
        )

    def test_session_move_other_lines_are_not_locked(self):
        move = self.env["account.move"].create(
            {
                "move_type": "entry",
                "journal_id": self.misc_journal.id,
                "date": fields.Date.today(),
                "line_ids": [
                    fields.Command.create(
                        {
                            "name": "POS receivable",
                            "account_id": self.account_pos_receivable.id,
                            "debit": 100.0,
                        }
                    ),
                    fields.Command.create(
                        {
                            "name": "Sales",
                            "account_id": self.account_income.id,
                            "credit": 100.0,
                        }
                    ),
                ],
            }
        )
        receivable_line = move.line_ids.filtered(
            lambda l: l.account_id == self.account_pos_receivable
        )
        sales_line = move.line_ids - receivable_line

        self.session.set_foreign_amount_in_line(receivable_line, 3650.0, 100.0)

        self.assertTrue(receivable_line.not_foreign_recalculate)
        self.assertEqual(receivable_line.foreign_debit, 3650.0)
        # A sales line of the session's closing move is not a counterpart of
        # the cash receivable: it must stay under the base compute.
        self.assertFalse(sales_line.not_foreign_recalculate)
