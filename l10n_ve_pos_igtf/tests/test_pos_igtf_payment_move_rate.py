"""IGTF in the entries that settle a POS invoice (tarea 83148, H18; Odoo 20).

Odoo 19 reimplemented ``pos.payment._create_payment_moves`` to split each
payment into its base (the receivable of the customer) and its IGTF
(``customer_account_igtf_id``). Odoo 20 creates the payment entry of the
invoice per payment method in core, so the payment line carries the whole
amount handed over, IGTF included, the ``payment_term`` line of the invoice
only the base, and the IGTF goes to its account in its own entry that is
reconciled together with them.

The entry keeps the convention of the rate of ``l10n_ve_pos``:
``foreign_inverse_rate`` = multiplier company -> alternate currency of the
payment and ``foreign_rate`` its inverse, with ``manually_set_rate``.
"""

from odoo import Command
from odoo.tests import tagged

from odoo.addons.l10n_ve_pos.tests.test_pos_session_accounting_common import (
    TestPosSessionAccountingBase,
)

RATE = 36.5
BASE = 116.0
IGTF = 3.48


@tagged("post_install", "-at_install", "l10n_ve_pos_igtf")
class TestPosIgtfPaymentMoveRate(TestPosSessionAccountingBase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._create_rate_of_day(1.0)
        cls.igtf_account = cls.env["account.account"].create(
            {
                "name": "C IGTF",
                "code": "210000C",
                "account_type": "liability_current",
                "company_ids": [(6, 0, [cls.company.id])],
            }
        )
        cls.company.write(
            {"customer_account_igtf_id": cls.igtf_account.id, "igtf_percentage": 3.0}
        )
        cls.config.closing_journal_id = cls.env["account.journal"].create(
            {
                "name": "C Closing",
                "type": "general",
                "code": "CCLO",
                "company_id": cls.company.id,
            }
        )

    def _order(self, igtf=IGTF, sign=1, refunded_line=None):
        session = self.env["pos.session"].search(
            [("config_id", "=", self.config.id)], limit=1
        ) or self.env["pos.session"].create(
            {"config_id": self.config.id, "user_id": self.env.ref("base.user_admin").id}
        )
        line = {
            "name": "OL/IGTF",
            "product_id": self.product.id,
            "price_unit": 100.0,
            "qty": sign * 1.0,
            "price_subtotal": sign * 100.0,
            "price_subtotal_incl": sign * BASE,
            "tax_ids": [Command.set(self.tax.ids)],
            "foreign_price": 100.0 * RATE,
        }
        if refunded_line:
            line["refunded_orderline_id"] = refunded_line.id
        return self.env["pos.order"].create(
            {
                "company_id": self.company.id,
                "session_id": session.id,
                "partner_id": self.company.partner_id.id,
                "pricelist_id": self.company.partner_id.property_product_pricelist.id,
                "foreign_amount_total": sign * BASE * RATE,
                "foreign_currency_rate": RATE,
                "lines": [Command.create(line)],
                "amount_total": sign * BASE,
                "amount_tax": sign * 16.0,
                "amount_paid": 0.0,
                "amount_return": 0.0,
                "igtf_amount": sign * igtf,
                "bi_igtf": sign * BASE if igtf else 0.0,
            }
        )

    def _pay(self, order, method, amount, igtf=0.0, sign=1):
        order.add_payment(
            {
                "name": "PAY",
                "pos_order_id": order.id,
                "amount": sign * amount,
                "payment_method_id": method.id,
                "payment_date": order.date_order,
                "foreign_amount": sign * amount * RATE,
                "foreign_rate": RATE,
                "foreign_currency_id": self.payment_currency.id,
                "amount_currency": sign * amount * RATE,
                "include_igtf": bool(igtf),
                "igtf_amount": sign * igtf,
                "foreign_igtf_amount": sign * igtf * RATE,
            }
        )
        return order.payment_ids.sorted("id")[-1]

    def _invoice(self, order):
        invoice = order.with_company(self.company)._generate_pos_order_invoice()
        term_lines = invoice.line_ids.filtered(lambda line: line.display_type == "payment_term")
        counterparts = (
            term_lines.matched_debit_ids.debit_move_id
            | term_lines.matched_credit_ids.credit_move_id
        ) - term_lines
        igtf_move = order.payment_ids.account_move_id
        return invoice, term_lines, counterparts.move_id | igtf_move, igtf_move

    def test_payment_move_rate_convention(self):
        order = self._order()
        self._pay(order, self.combined_bank_method, BASE + IGTF, igtf=IGTF)

        invoice, term_lines, payment_moves, igtf_move = self._invoice(order)

        self.assertEqual(len(igtf_move), 1)
        self.assertAlmostEqual(igtf_move.foreign_inverse_rate, RATE, places=12)
        self.assertAlmostEqual(igtf_move.foreign_rate, 1 / RATE, places=6)
        self.assertTrue(igtf_move.manually_set_rate)

    def test_invoice_owes_only_the_base_and_igtf_has_its_account(self):
        order = self._order()
        payment = self._pay(order, self.combined_bank_method, BASE + IGTF, igtf=IGTF)

        invoice, term_lines, payment_moves, igtf_move = self._invoice(order)

        self.assertAlmostEqual(sum(term_lines.mapped("balance")), BASE)
        self.assertAlmostEqual(invoice.amount_total, BASE)
        self.assertEqual(invoice.payment_state, "paid")
        self.assertTrue(invoice.currency_id.is_zero(invoice.amount_residual))
        igtf_line = igtf_move.line_ids.filtered(lambda line: line.account_id == self.igtf_account)
        self.assertAlmostEqual(igtf_line.credit, IGTF)
        self.assertEqual(igtf_line.partner_id, self.company.partner_id)
        receivable_line = igtf_move.line_ids - igtf_line
        self.assertAlmostEqual(receivable_line.debit, IGTF)
        self.assertEqual(igtf_move.journal_id, self.config.closing_journal_id)
        self.assertEqual(igtf_move.state, "posted")
        self.assertEqual(payment.account_move_id, igtf_move)

    def test_igtf_move_carries_the_alternate_amount_of_the_igtf(self):
        order = self._order()
        self._pay(order, self.combined_bank_method, BASE + IGTF, igtf=IGTF)

        invoice, term_lines, payment_moves, igtf_move = self._invoice(order)

        for line in igtf_move.line_ids:
            self.assertAlmostEqual(line.foreign_debit + line.foreign_credit, IGTF * RATE, places=2)
            self.assertTrue(line.not_foreign_recalculate)
        self.assertAlmostEqual(sum(igtf_move.line_ids.mapped("foreign_balance")), 0.0, places=2)

    def test_everything_reconciles_with_the_igtf_on_its_account(self):
        order = self._order()
        self._pay(order, self.combined_bank_method, BASE + IGTF, igtf=IGTF)

        invoice, term_lines, payment_moves, igtf_move = self._invoice(order)

        receivable = payment_moves.line_ids.filtered(
            lambda line: line.account_id.account_type == "asset_receivable"
        ) | term_lines
        self.assertTrue(all(receivable.mapped("reconciled")))
        self.assertAlmostEqual(sum(receivable.mapped("balance")), 0.0)

    def test_igtf_of_two_methods_is_settled_per_method(self):
        order = self._order(igtf=IGTF)
        half_base = BASE / 2
        half_igtf = IGTF / 2
        self._pay(order, self.combined_bank_method, half_base + half_igtf, igtf=half_igtf)
        self._pay(order, self.split_bank_method, half_base + half_igtf, igtf=half_igtf)

        invoice, term_lines, payment_moves, igtf_move = self._invoice(order)

        self.assertEqual(len(igtf_move), 2)
        self.assertAlmostEqual(sum(igtf_move.line_ids.mapped("credit")), IGTF)
        self.assertEqual(invoice.payment_state, "paid")

    def test_payment_without_igtf_leaves_the_invoice_as_core_builds_it(self):
        order = self._order(igtf=0.0)
        self._pay(order, self.combined_bank_method, BASE)

        invoice, term_lines, payment_moves, igtf_move = self._invoice(order)

        self.assertFalse(igtf_move)
        self.assertAlmostEqual(sum(term_lines.mapped("balance")), BASE)
        self.assertEqual(invoice.payment_state, "paid")

    def test_refund_reverses_the_igtf(self):
        original = self._order(igtf=0.0)
        order = self._order(sign=-1, refunded_line=original.lines)
        self._pay(order, self.combined_bank_method, BASE + IGTF, igtf=IGTF, sign=-1)

        invoice, term_lines, payment_moves, igtf_move = self._invoice(order)

        self.assertAlmostEqual(sum(term_lines.mapped("balance")), -BASE)
        self.assertEqual(invoice.move_type, "out_refund")
        self.assertFalse(invoice.bi_igtf)
        self.assertFalse(invoice.alter_bi_igtf)
        self.assertFalse(invoice.igtf_top_aply)
        igtf_line = igtf_move.line_ids.filtered(lambda line: line.account_id == self.igtf_account)
        self.assertAlmostEqual(igtf_line.debit, IGTF)
        self.assertAlmostEqual((igtf_move.line_ids - igtf_line).credit, IGTF)
        self.assertEqual(invoice.payment_state, "paid")

    def test_closing_entries_are_built_as_core_does(self):
        order = self._order()
        payment = self._pay(order, self.combined_bank_method, BASE + IGTF, igtf=IGTF)

        entries = order._prepare_account_move_line_data_for_payments()

        self.assertEqual(len(entries), 1)
        self.assertAlmostEqual(entries[0]["account.move.line"]["amount_currency"], BASE + IGTF)
        self.assertAlmostEqual(entries[0]["metadata"]["igtf_amount"], IGTF)
        self.assertEqual(entries[0]["metadata"]["payments"], payment)

    def test_invoice_igtf_fields_come_from_the_order(self):
        order = self._order()
        self._pay(order, self.combined_bank_method, BASE + IGTF, igtf=IGTF)

        invoice, term_lines, payment_moves, igtf_move = self._invoice(order)

        self.assertAlmostEqual(invoice.bi_igtf, BASE)
        self.assertAlmostEqual(invoice.alter_bi_igtf, IGTF)
        self.assertAlmostEqual(invoice.igtf_top_aply, BASE * 0.03)

    def test_order_is_paid_when_the_payments_cover_total_plus_igtf(self):
        order = self._order()
        self._pay(order, self.combined_bank_method, BASE + IGTF, igtf=IGTF)
        order.amount_paid = BASE + IGTF

        self.assertAlmostEqual(order._get_total_with_igtf(), BASE + IGTF)
        self.assertTrue(order.action_pos_order_paid())
        self.assertEqual(order.state, "paid")
