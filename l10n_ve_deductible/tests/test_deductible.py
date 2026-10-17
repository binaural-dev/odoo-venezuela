from odoo import Command, fields
from odoo.exceptions import ValidationError
from odoo.tests import Form, TransactionCase, tagged

from .common import AssertMixin, ensure_ve_base


@tagged("post_install", "-at_install", "l10n_ve_deductible")
class TestDeductible(AssertMixin, TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ensure_ve_base(cls.env)
        cls.company = cls.env.company
        cls.company.use_deductible = True
        cls.partner = cls.env["res.partner"].create({"name": "Proveedor Deducible"})
        cls.product = cls.env["product.product"].create({"name": "Producto Deducible"})
        cls.exempt_tax = cls.env["account.tax"].create(
            {
                "name": "Exento Test",
                "amount_type": "percent",
                "amount": 0.0,
                "type_tax_use": "purchase",
            }
        )
        cls.general_tax = cls.env["account.tax"].create(
            {
                "name": "General Test",
                "amount_type": "percent",
                "amount": 16.0,
                "type_tax_use": "purchase",
            }
        )

    def _bill(self, prices=(100.0, 300.0), tax=None, **vals):
        tax = tax or self.exempt_tax
        return self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.partner.id,
                "invoice_date": fields.Date.today(),
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "name": f"L{i}",
                            "quantity": 1,
                            "price_unit": price,
                            "tax_ids": [Command.set(tax.ids)],
                        }
                    )
                    for i, price in enumerate(prices)
                ],
                **vals,
            }
        )

    def test_percent_total(self):
        bill = self._bill(is_deductible=True, global_deductible_type="percent", global_deductible_percent=10.0)
        self.assertEqual(bill.amount_total, 360.0)
        self.assertEqual(bill.global_deductible_reference_amount, 40.0)

    def test_amount_total_proportional(self):
        bill = self._bill(
            prices=(100.0, 200.0, 300.0),
            is_deductible=True,
            global_deductible_type="amount",
            global_deductible_amount=100.0,
        )
        self.assertEqual(bill.amount_total, 500.0)
        self.assertEqual(
            round(sum(bill._get_deductible_line_amounts().values()), 4), 100.0
        )

    def test_amount_cannot_reach_total(self):
        with self.assertRaisesMsg(ValidationError, "less than the original bill total"):
            self._bill(is_deductible=True, global_deductible_type="amount", global_deductible_amount=400.0)
        with self.assertRaisesMsg(ValidationError, "less than the original bill total"):
            self._bill(is_deductible=True, global_deductible_type="amount", global_deductible_amount=500.0)

    def test_percent_bounds(self):
        with self.assertRaisesMsg(ValidationError, "greater than 0 and less than 100"):
            self._bill(is_deductible=True, global_deductible_type="percent", global_deductible_percent=100.0)
        with self.assertRaisesMsg(ValidationError, "greater than 0 and less than 100"):
            self._bill(is_deductible=True, global_deductible_type="percent", global_deductible_percent=0.0)

    def test_requires_exempt_tax(self):
        with self.assertRaisesMsg(ValidationError, "exempt tax"):
            self._bill(
                tax=self.general_tax,
                is_deductible=True,
                global_deductible_type="percent",
                global_deductible_percent=10.0,
            )

    def test_previous_discount_blocked(self):
        bill = self._bill(is_deductible=True, global_deductible_type="percent", global_deductible_percent=10.0)
        with self.assertRaisesMsg(ValidationError, "cannot have lines with a discount"):
            bill.invoice_line_ids[0].discount = 5.0

    def test_only_vendor_bills(self):
        with self.assertRaisesMsg(ValidationError, "only be used on vendor bills"):
            self.env["account.move"].create(
                {
                    "move_type": "out_invoice",
                    "partner_id": self.partner.id,
                    "is_deductible": True,
                    "global_deductible_type": "percent",
                    "global_deductible_percent": 10.0,
                    "invoice_line_ids": [
                        Command.create(
                            {"product_id": self.product.id, "name": "x", "price_unit": 10.0, "tax_ids": [Command.set(self.exempt_tax.ids)]}
                        )
                    ],
                }
            )

    def test_onchange_blocks_activation_with_taxed_line(self):
        bill = self._bill(tax=self.general_tax)
        res = bill.onchange(
            {"is_deductible": True}, ["is_deductible"], {"is_deductible": {}}
        )
        self.assertIn("warning", res)
        self.assertFalse(res["value"].get("is_deductible", False))

    def test_tax_totals_deductible_rows(self):
        bill = self._bill(is_deductible=True, global_deductible_type="percent", global_deductible_percent=10.0)
        totals = bill.tax_totals
        self.assertTrue(totals.get("is_deductible"))
        for key in (
            "formatted_deductible_original_currency",
            "formatted_deductible_amount_currency",
            "formatted_deductible_original_foreign",
            "formatted_deductible_amount_foreign",
            "formatted_deductible_original_ves",
            "formatted_deductible_amount_ves",
        ):
            self.assertIn(key, totals)
        self.assertIn("400.00", totals["formatted_deductible_original_currency"])
        self.assertIn("40.00", totals["formatted_deductible_amount_currency"])

    def test_tax_totals_without_deductible(self):
        bill = self._bill()
        self.assertFalse(bill.tax_totals.get("is_deductible"))
