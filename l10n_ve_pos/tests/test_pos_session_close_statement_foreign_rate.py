"""Ticket #15169: the cash statement booked by the session closing must keep
the alternate-currency double entry when the BCV rate changed between the
sale and the closing.

The closing stamps the sale-time ``foreign_amount`` on the POS receivable leg
of the cash statement and on its cash leg. The cash leg must be locked too
(``not_foreign_recalculate``); otherwise ``l10n_ve_accountant`` recomputes it
at the rate of the move date (the closing day) and the statement ends up with
foreign debit != foreign credit.
"""

from odoo.tests import tagged

from .test_pos_session_accounting_common import TestPosSessionClosingBase


@tagged("post_install", "-at_install", "l10n_ve_pos", "pos_close_statement_foreign_rate")
class TestPosSessionCloseStatementForeignRate(TestPosSessionClosingBase):
    def _close_with_cash_sale(self):
        session = self._open_session()
        # Sale valued at 36.5 while the closing day is at 1.0.
        self._create_paid_order(
            session,
            method=self.cash_method,
            amount=116.0,
            tax_amount=16.0,
            foreign_rate=36.5,
            name="OL/STMT/1",
        )
        return self._close(session, 116.0)

    def test_statement_cash_leg_keeps_sale_foreign_amount(self):
        session = self._close_with_cash_sale()
        sale_foreign_amount = 4234.0

        term_line = session.sale_move_ids.line_ids.filtered(
            lambda line: line.display_type == "payment_term"
        )
        statement_lines = (
            term_line.matched_debit_ids.debit_move_id
            | term_line.matched_credit_ids.credit_move_id
        ).move_id.line_ids - term_line
        cash_line = statement_lines.filtered(
            lambda line: line.account_id == self.account_cash
        )
        receivable_line = statement_lines - cash_line

        self.assertTrue(cash_line.not_foreign_recalculate)
        self.assertEqual(receivable_line.foreign_credit, sale_foreign_amount)
        self.assertEqual(cash_line.foreign_debit, sale_foreign_amount)
        self.assertEqual(
            sum(statement_lines.mapped("foreign_debit")),
            sum(statement_lines.mapped("foreign_credit")),
            "the cash statement must balance in the alternate currency",
        )

    def test_session_move_stays_balanced_in_the_alternate_currency(self):
        session = self._close_with_cash_sale()

        move = session.sale_move_ids
        term_line = move.line_ids.filtered(
            lambda line: line.display_type == "payment_term"
        )
        # The term line carries what the register charged, and the sales and
        # tax lines are scaled to it: the closing day is at 1.0, the sale at 36.5.
        self.assertEqual(term_line.foreign_debit, 4234.0)
        self.assertEqual(
            sum(move.line_ids.mapped("foreign_debit")),
            sum(move.line_ids.mapped("foreign_credit")),
        )
