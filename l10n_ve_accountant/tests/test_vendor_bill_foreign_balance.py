# Ticket #15694: vendor bills unbalanced in USD (payment term line with 0, a stale amount, or
# a rounding gap against the product + tax lines).
from odoo import Command, fields
from odoo.tests import TransactionCase, tagged
from odoo.tools import float_is_zero


@tagged("post_install", "-at_install", "l10n_ve_vendor_bill_foreign_balance")
class TestVendorBillForeignBalance(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.vef = cls.env.ref("base.VEF")
        cls.usd = cls.env.ref("base.USD")
        cls.company = cls.env.ref("base.main_company")
        cls.company.write({"currency_id": cls.vef.id, "currency_foreign_id": cls.usd.id})
        cls.rate = cls.env["res.currency.rate"].create({
            "name": fields.Date.today(), "currency_id": cls.usd.id,
            "inverse_company_rate": 50.0, "company_id": cls.company.id,
        })
        cls.partner = cls.env["res.partner"].create({"name": "Vendor 15694"})
        cls.journal = cls.env["account.journal"].search(
            [("type", "=", "purchase"), ("company_id", "=", cls.company.id)], limit=1)
        cls.product = cls.env["product.product"].create({"name": "Svc 15694", "type": "service"})
        cls.tax = cls.env["account.tax"].create({
            "name": "IVA 16 compras 15694", "amount": 16.0, "amount_type": "percent",
            "type_tax_use": "purchase", "company_id": cls.company.id,
        })

    def _bill(self, prices, post=False, payment_term=None):
        bill = self.env["account.move"].create({
            "move_type": "in_invoice", "partner_id": self.partner.id,
            "journal_id": self.journal.id, "invoice_date": fields.Date.today(),
            "invoice_payment_term_id": payment_term.id if payment_term else False,
            "invoice_line_ids": [
                Command.create({
                    "product_id": self.product.id, "name": "Line", "quantity": 1,
                    "price_unit": price, "tax_ids": [Command.set(self.tax.ids)],
                }) for price in prices
            ],
        })
        if post:
            bill.action_post()
        return bill

    def _usd_diff(self, bill):
        self.env.flush_all()
        return sum(bill.line_ids.mapped("foreign_debit")) - sum(bill.line_ids.mapped("foreign_credit"))

    def _assert_balanced_usd(self, bill):
        diff = self._usd_diff(bill)
        self.assertTrue(
            float_is_zero(diff, precision_rounding=self.usd.rounding),
            f"Bill unbalanced in USD by {diff}",
        )

    def _payment_term_usd(self, bill):
        pt = bill.line_ids.filtered(lambda l: l.display_type == "payment_term")
        return sum(pt.mapped("foreign_credit")) - sum(pt.mapped("foreign_debit"))

    def test_rounding_gap_is_absorbed_in_draft(self):
        """Per-line USD rounding must not leave the bill unbalanced (81 cases < 1 USD)."""
        bill = self._bill([5033.50, 1234.57, 987.65, 4321.09])
        self._assert_balanced_usd(bill)

    def test_rounding_gap_is_absorbed_when_posted(self):
        bill = self._bill([5033.50, 1234.57, 987.65, 4321.09], post=True)
        self._assert_balanced_usd(bill)

    def test_payment_term_is_never_zero_when_products_have_amount(self):
        """8 production bills had the CxP in 0 USD while products had an amount."""
        bill = self._bill([300000.0], post=True)
        # 300000 Bs + 16 % tax = 348000 Bs / 50
        self.assertAlmostEqual(self._payment_term_usd(bill), 6960.0, places=2)
        self._assert_balanced_usd(bill)

    def test_payment_term_follows_a_price_change(self):
        bill = self._bill([5000.0])
        self.assertAlmostEqual(self._payment_term_usd(bill), 116.0, places=2)
        bill.invoice_line_ids[0].price_unit = 10000.0
        self.env.flush_all()
        # doubled price: 11600 Bs / 50
        self.assertAlmostEqual(self._payment_term_usd(bill), 232.0, places=2)
        self._assert_balanced_usd(bill)

    def test_payment_term_follows_a_rate_change(self):
        """2 production bills kept the CxP with an old amount/rate."""
        bill = self._bill([5000.0])
        bill.write({"manually_set_rate": True, "foreign_rate": 100.0, "foreign_inverse_rate": 0.01})
        bill.invoice_line_ids.write({"price_unit": 5000.0})
        self.env.flush_all()
        self._assert_balanced_usd(bill)
        # products (5000 Bs / 100) + 16 % tax = 58.00 USD on the CxP
        self.assertAlmostEqual(self._payment_term_usd(bill), 58.0, places=2)

    def test_split_payment_term_is_balanced_in_usd(self):
        """Several instalments: the rounding gap must be spread without unbalancing the bill."""
        term = self.env["account.payment.term"].create({
            "name": "Three instalments 15694",
            "line_ids": [
                Command.create({"value": "percent", "value_amount": 33.33, "nb_days": 0}),
                Command.create({"value": "percent", "value_amount": 33.33, "nb_days": 30}),
                Command.create({"value": "percent", "value_amount": 33.34, "nb_days": 60}),
            ],
        })
        bill = self._bill([5033.50, 1234.57, 987.65, 4321.09], payment_term=term)
        pt = bill.line_ids.filtered(lambda l: l.display_type == "payment_term")
        self.assertEqual(len(pt), 3)
        self._assert_balanced_usd(bill)
        total = bill.currency_id.round(bill.amount_total / 50.0)
        self.assertAlmostEqual(self._payment_term_usd(bill), total, delta=self.usd.rounding)
        bill.action_post()
        self._assert_balanced_usd(bill)

    def test_rounding_gap_never_lands_on_the_tax_line(self):
        """The tax line keeps its own per-line USD conversion; the gap goes to PT/product lines."""
        bill = self._bill([5033.50, 1234.57, 987.65, 4321.09])
        self.env.flush_all()
        tax_line = bill.line_ids.filtered(lambda l: l.display_type == "tax")
        self.assertTrue(tax_line)
        expected = self.usd.round(abs(tax_line.balance) / 50.0)
        self.assertAlmostEqual(abs(tax_line.foreign_balance), expected, places=2)
