from odoo import Command, fields
from odoo.tests import TransactionCase, tagged

from .common import ensure_ve_base


@tagged("post_install", "-at_install", "l10n_ve_deductible")
class TestDeductibleMultiCurrency(TransactionCase):
    """Company (base) currency VEF, alternate currency USD, 1 USD = 38 VEF."""

    LINES = [(10.3333, 3), (7.1249, 7), (0.9999, 13), (123.4567, 1), (3.3333, 9)]
    RATE = 38.0

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ensure_ve_base(cls.env)
        cls.env.ref("product.decimal_price").digits = 4
        cls.vef = cls.env.ref("base.VEF")
        cls.usd = cls.env.ref("base.USD")
        cls.company = cls.env.company
        cls.company.write({"use_deductible": True})
        today = fields.Date.today()
        Rate = cls.env["res.currency.rate"]
        Rate.create({"name": today, "currency_id": cls.vef.id,
                     "inverse_company_rate": 1.0, "company_id": cls.company.id})
        Rate.create({"name": today, "currency_id": cls.usd.id,
                     "inverse_company_rate": cls.RATE, "company_id": cls.company.id})
        cls.partner = cls.env["res.partner"].create({"name": "Proveedor MC"})
        cls.exempt = cls.env["account.tax"].create(
            {"name": "Ex MC", "amount_type": "percent", "amount": 0.0, "type_tax_use": "purchase"}
        )
        cls.product = cls.env["product.product"].create(
            {"name": "Prod MC", "supplier_taxes_id": [Command.set(cls.exempt.ids)]}
        )
        cls.gross = sum(p * q for p, q in cls.LINES)

    @staticmethod
    def _ves(text):
        return float(text.split("\xa0")[0].replace(",", ""))

    def _bill(self, currency, **vals):
        return self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.partner.id,
                "currency_id": currency.id,
                "invoice_date": fields.Date.today(),
                "invoice_line_ids": [
                    Command.create(
                        {"product_id": self.product.id, "name": f"L{i}", "quantity": q,
                         "price_unit": p, "tax_ids": [Command.set(self.exempt.ids)]}
                    )
                    for i, (p, q) in enumerate(self.LINES)
                ],
                **vals,
            }
        )

    def _check(self, bill, deducted):
        """Everything must be consistent in the three currencies."""
        doc_rate = 1.0 if bill.currency_id == self.vef else 1.0 / self.RATE
        self.assertEqual(bill.amount_untaxed, bill.currency_id.round(self.gross - deducted))
        ves_deducted = deducted / doc_rate
        self.assertEqual(
            round(abs(bill.amount_total_signed), 2),
            self.vef.round(bill.amount_untaxed / doc_rate) if bill.currency_id == self.usd
            else bill.amount_untaxed,
        )
        totals = bill.tax_totals
        self.assertTrue(totals["is_deductible"])
        self.assertEqual(
            round(totals["base_amount"], 2), round(abs(bill.amount_total_signed), 2)
        )
        return totals, ves_deducted

    def test_bill_in_vef_amount(self):
        bill = self._bill(self.vef, is_deductible=True,
                          global_deductible_type="amount", global_deductible_amount=77.77)
        self.assertEqual(bill.foreign_currency_id, self.usd)
        totals, _ves = self._check(bill, 77.77)
        self.assertIn("77.77", totals["formatted_deductible_amount_currency"])
        self.assertIn("77.77", totals["formatted_deductible_amount_ves"])
        self.assertIn("2.05", totals["formatted_deductible_amount_foreign"])
        self.assertIn("2.05", totals["formatted_deductible_amount_foreign"])

    def test_bill_in_usd_amount(self):
        bill = self._bill(self.usd, is_deductible=True,
                          global_deductible_type="amount", global_deductible_amount=77.77)
        totals, _ves = self._check(bill, 77.77)
        self.assertIn("77.77", totals["formatted_deductible_amount_currency"])
        self.assertIn("77.77", totals["formatted_deductible_amount_foreign"])
        self.assertIn("2,955.26", totals["formatted_deductible_amount_ves"])
        self.assertEqual(
            round(self._ves(totals["formatted_deductible_original_ves"])
                  - self._ves(totals["formatted_deductible_amount_ves"]), 2),
            round(totals["base_amount"], 2),
        )

    def test_bill_in_vef_percent_and_changes(self):
        bill = self._bill(self.vef, is_deductible=True,
                          global_deductible_type="percent", global_deductible_percent=12.5)
        self._check(bill, self.gross * 0.125)
        bill.invoice_line_ids[0].price_unit = 55.5555
        bill.write({"invoice_line_ids": [Command.create(
            {"product_id": self.product.id, "name": "N", "quantity": 4, "price_unit": 19.9876,
             "tax_ids": [Command.set(self.exempt.ids)]})]})
        self.gross = sum(l.price_unit * l.quantity for l in bill.invoice_line_ids)
        self._check(bill, self.gross * 0.125)
        bill.is_deductible = False
        self.assertEqual(bill.amount_untaxed, bill.currency_id.round(self.gross))

