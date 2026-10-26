# Ticket #15732: vendor bills unbalanced in USD (payment term line with 0, a stale amount, or
# a rounding gap against the product + tax lines).
from odoo import Command, fields
from odoo.tests import TransactionCase, tagged


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
        cls.partner = cls.env["res.partner"].create({"name": "Vendor 15732"})
        cls.journal = cls.env["account.journal"].search(
            [("type", "=", "purchase"), ("company_id", "=", cls.company.id)], limit=1)
        cls.product = cls.env["product.product"].create({"name": "Svc 15732", "type": "service"})
        cls.tax = cls.env["account.tax"].create({
            "name": "IVA 16 compras 15732", "amount": 16.0, "amount_type": "percent",
            "type_tax_use": "purchase", "company_id": cls.company.id,
        })

    def _bill(self, prices, post=False):
        bill = self.env["account.move"].create({
            "move_type": "in_invoice", "partner_id": self.partner.id,
            "journal_id": self.journal.id, "invoice_date": fields.Date.today(),
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
        return round(sum(bill.line_ids.mapped("foreign_debit"))
                     - sum(bill.line_ids.mapped("foreign_credit")), 2)

    def _payment_term_usd(self, bill):
        pt = bill.line_ids.filtered(lambda l: l.display_type == "payment_term")
        return sum(pt.mapped("foreign_credit")) - sum(pt.mapped("foreign_debit"))

    def test_rounding_gap_is_absorbed_in_draft(self):
        """Per-line USD rounding must not leave the bill unbalanced (81 cases < 1 USD)."""
        bill = self._bill([5033.50, 1234.57, 987.65, 4321.09])
        self.assertEqual(self._usd_diff(bill), 0.0)

    def test_rounding_gap_is_absorbed_when_posted(self):
        bill = self._bill([5033.50, 1234.57, 987.65, 4321.09], post=True)
        self.assertEqual(self._usd_diff(bill), 0.0)

    def test_payment_term_is_never_zero_when_products_have_amount(self):
        """8 production bills had the CxP in 0 USD while products had an amount."""
        bill = self._bill([300000.0], post=True)
        self.assertGreater(self._payment_term_usd(bill), 0.0)
        self.assertEqual(self._usd_diff(bill), 0.0)

    def test_payment_term_follows_a_price_change(self):
        bill = self._bill([5000.0])
        before = self._payment_term_usd(bill)
        bill.invoice_line_ids[0].price_unit = 10000.0
        self.env.flush_all()
        self.assertGreater(self._payment_term_usd(bill), before)
        self.assertEqual(self._usd_diff(bill), 0.0)

    def test_payment_term_follows_a_rate_change(self):
        """2 production bills kept the CxP with an old amount/rate."""
        bill = self._bill([5000.0])
        bill.write({"foreign_rate": 100.0, "foreign_inverse_rate": 0.01})
        bill.invoice_line_ids.write({"price_unit": 5000.0})
        self.env.flush_all()
        self.assertEqual(self._usd_diff(bill), 0.0)
        # products (5000 Bs / 100) + 16 % tax = 58.00 USD on the CxP
        self.assertAlmostEqual(self._payment_term_usd(bill), 58.0, places=2)
