"""Alternate amounts the session closing leaves on its entries (Odoo 20).

Odoo 20 closes a session in one pipeline: ``_create_session_account_move``
builds the closing entry with one ``payment_term`` line per payment method and
then creates and reconciles, per line, the cash statement line or the
``account.payment`` that settles it. ``l10n_ve_pos`` stamps on every one of
those lines the alternate amount the register charged
(``pos.payment.foreign_amount``), because ``l10n_ve_accountant`` would value
them at the rate of the closing day.

The ``payment_term`` lines of the closing entry carry the same alternate
amount as the payments they group, as Odoo 19 stamped them: left to
``l10n_ve_accountant`` they would be valued at the rate of the closing day and
the payments (which keep the rate of the sale) would leave an exchange
difference entry at the reconciliation.

These tests replace the ones of the Odoo 19 accumulators
(``_accumulate_amounts``, ``_create_bank_payment_moves``, ...), which no longer
exist: they check the result on the entries, not the intermediate dicts.
"""

from unittest.mock import patch

from odoo.tests import tagged

from .test_pos_session_accounting_common import TestPosSessionClosingBase


@tagged("post_install", "-at_install", "l10n_ve_pos", "pos_close_foreign_amounts")
class TestPosSessionCloseForeignAmounts(TestPosSessionClosingBase):
    def _foreign(self, line):
        return line.foreign_debit + line.foreign_credit

    def _term_lines(self, session):
        return session.sale_move_ids.line_ids.filtered(
            lambda line: line.display_type == "payment_term"
        )

    def _settlement_lines(self, term_line):
        counterparts = (
            term_line.matched_debit_ids.debit_move_id
            | term_line.matched_credit_ids.credit_move_id
        ) - term_line
        payment_moves = counterparts.move_id.filtered(
            lambda move: move.journal_id != self.company.currency_exchange_journal_id
        )
        return payment_moves.line_ids

    def test_cash_payments_carry_their_foreign_amount(self):
        session = self._open_session()
        self._create_paid_order(
            session, method=self.cash_method, amount=116.0, name="OL/F/1"
        )
        self._create_paid_order(
            session,
            method=self.cash_method,
            amount=58.0,
            tax_amount=8.0,
            foreign_rate=40.0,
            name="OL/F/2",
        )
        self._close(session, 174.0)

        term_lines = self._term_lines(session)
        self.assertEqual(len(term_lines), 1)
        expected = 116.0 * 36.5 + 58.0 * 40.0
        self.assertAlmostEqual(self._foreign(term_lines), expected, places=2)
        self.assertTrue(term_lines.not_foreign_recalculate)
        settlement = self._settlement_lines(term_lines)
        self.assertEqual(len(settlement), 2)
        for line in settlement:
            self.assertAlmostEqual(self._foreign(line), expected, places=2)
            self.assertTrue(line.not_foreign_recalculate)

    def test_bank_payments_carry_their_foreign_amount(self):
        session = self._open_session()
        self._create_paid_order(
            session, method=self.bank_method, amount=116.0, name="OL/F/B1"
        )
        self._create_paid_order(
            session,
            method=self.bank_method,
            amount=58.0,
            tax_amount=8.0,
            name="OL/F/B2",
        )
        self._close(session, 0.0)

        term_lines = self._term_lines(session)
        self.assertEqual(len(term_lines), 1)
        expected = (116.0 + 58.0) * 36.5
        self.assertAlmostEqual(self._foreign(term_lines), expected, places=2)
        settlement = self._settlement_lines(term_lines)
        self.assertEqual(len(settlement), 2)
        for line in settlement:
            self.assertAlmostEqual(self._foreign(line), expected, places=2)
        payment = settlement.move_id.origin_payment_id
        self.assertTrue(payment)
        self.assertAlmostEqual(payment.foreign_rate, session.config_id.foreign_rate)

    def test_each_method_keeps_its_own_foreign_amount(self):
        session = self._open_session()
        self._create_paid_order(
            session, method=self.cash_method, amount=116.0, name="OL/F/M1"
        )
        self._create_paid_order(
            session,
            method=self.bank_method,
            amount=58.0,
            tax_amount=8.0,
            foreign_rate=40.0,
            name="OL/F/M2",
        )
        self._close(session, 116.0)

        by_foreign = sorted(
            self._foreign(self._settlement_lines(term_line)[:1])
            for term_line in self._term_lines(session)
        )
        self.assertEqual(len(by_foreign), 2)
        self.assertAlmostEqual(by_foreign[0], 58.0 * 40.0, places=2)
        self.assertAlmostEqual(by_foreign[1], 116.0 * 36.5, places=2)

    def test_no_exchange_difference_entry_when_the_rate_moved_after_the_sale(self):
        session = self._open_session()
        self._create_paid_order(
            session, method=self.cash_method, amount=116.0, name="OL/F/E1"
        )
        self._create_paid_order(
            session, method=self.bank_method, amount=58.0, tax_amount=8.0, name="OL/F/E2"
        )
        self._close(session, 116.0)

        exchange_moves = self.env["account.move"].search(
            [("journal_id", "=", self.company.currency_exchange_journal_id.id)]
        )
        self.assertFalse(exchange_moves)

    def test_closing_entry_takes_the_rate_of_the_config(self):
        session = self._open_session()
        self._create_paid_order(
            session, method=self.cash_method, amount=116.0, name="OL/F/R1"
        )
        self._close(session, 116.0)

        move = session.sale_move_ids
        self.assertAlmostEqual(move.foreign_rate, session.config_id.foreign_rate)
        self.assertAlmostEqual(
            move.foreign_inverse_rate, session.config_id.foreign_inverse_rate
        )

    def test_closing_creates_the_cross_moves(self):
        session = self._open_session()
        self._create_paid_order(
            session, method=self.cash_method, amount=116.0, name="OL/F/X1"
        )
        with patch.object(type(self.env["pos.session"]), "_validate_cross_move") as cross_move:
            self._close(session, 116.0)

        cross_move.assert_called_once()

    def test_invoiced_order_payments_carry_rate_and_foreign_amount(self):
        session = self._open_session()
        order = self._create_paid_order(
            session, method=self.cash_method, amount=116.0, name="OL/F/I1"
        )
        invoice = order.with_company(self.company)._generate_pos_order_invoice()

        term_lines = invoice.line_ids.filtered(
            lambda line: line.display_type == "payment_term"
        )
        self.assertEqual(len(term_lines), 1)
        settlement = self._settlement_lines(term_lines)
        self.assertEqual(len(settlement), 2)
        for line in settlement:
            self.assertAlmostEqual(self._foreign(line), 116.0 * 36.5, places=2)
        payment_move = settlement.move_id
        self.assertTrue(payment_move.manually_set_rate)
        self.assertAlmostEqual(payment_move.foreign_inverse_rate, 36.5, places=12)

    def test_invoiced_order_change_is_netted_in_the_payment_entry(self):
        session = self._open_session()
        order = self._create_paid_order(
            session, method=self.cash_method, amount=120.0, name="OL/F/I2"
        )
        order.write({"amount_total": 116.0, "amount_paid": 120.0})
        order.add_payment(
            {
                "name": "CHANGE",
                "pos_order_id": order.id,
                "amount": -4.0,
                "payment_method_id": self.cash_method.id,
                "payment_date": order.date_order,
                "is_change": True,
                "foreign_amount": order._amount_to_foreign(-4.0),
                "foreign_rate": 36.5,
            }
        )
        invoice = order.with_company(self.company)._generate_pos_order_invoice()

        term_lines = invoice.line_ids.filtered(
            lambda line: line.display_type == "payment_term"
        )
        self.assertEqual(len(term_lines), 1)
        settlement = self._settlement_lines(term_lines)
        expected = 120.0 * 36.5 - 4.0 * 36.5
        for line in settlement:
            self.assertAlmostEqual(self._foreign(line), expected, places=2)
