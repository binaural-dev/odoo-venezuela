from odoo.tests import tagged
from odoo import Command
from .common import AccountRetentionTestCommon
from odoo.tools import float_compare


@tagged("post_install", "-at_install", "iva_retention", "base_vef_retention")
class TestIvaRetentionBs(AccountRetentionTestCommon):
    def test_account_retention_line_compute_vef_base(self):
        """
        Test that the retention line data is computed correctly for a given invoice with base.VEF
        as the company currency and base.USD as the foreign currency.
        """
        invoice = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.partner_a.id,
                "foreign_currency_id": self.company_data["company"].currency_foreign_id.id,
                "foreign_rate": 20,
                "foreign_inverse_rate": 0.05,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": self.product_a.id,
                            "quantity": 1,
                            "price_unit": 100,
                            "tax_ids": [Command.link(self.tax_purchase_a.id)],
                        }
                    ),
                    Command.create(
                        {
                            "product_id": self.product_b.id,
                            "quantity": 1,
                            "price_unit": 50,
                            "tax_ids": [Command.link(self.tax_purchase_b.id)],
                        }
                    ),
                    Command.create(
                        {
                            "product_id": self.product_c.id,
                            "quantity": 1,
                            "price_unit": 100,
                            "tax_ids": [Command.link(self.tax_purchase_a.id)],
                        }
                    ),
                    Command.create(
                        {
                            "product_id": self.product_d.id,
                            "quantity": 1,
                            "price_unit": 100,
                            "tax_ids": [Command.link(self.tax_purchase_c.id)],
                        }
                    ),
                    Command.create(
                        {
                            "product_id": self.product_e.id,
                            "quantity": 1,
                            "price_unit": 100,
                            "tax_ids": [Command.link(self.tax_purchase_d.id)],
                        }
                    ),
                ],
            }
        )
        retention_lines_data = self.Retention.compute_retention_lines_data(
            invoice, ("iva", "in_invoice")
        )

        self.assertEqual(len(retention_lines_data), 3)

        # Testing each value instead of the whole list because we need to compare floats
        # if this pattern is repeated, we should create a helper method to compare the whole list
        self.assertEqual(retention_lines_data[0]["aliquot"], 16)
        self.assertEqual(float_compare(retention_lines_data[0]["retention_amount"], 24, 2), 0)
        self.assertEqual(
            float_compare(retention_lines_data[0]["foreign_retention_amount"], 1.2, 2), 0
        )
        self.assertEqual(retention_lines_data[1]["aliquot"], 8)
        self.assertEqual(float_compare(retention_lines_data[1]["retention_amount"], 6, 2), 0)
        self.assertEqual(
            float_compare(retention_lines_data[1]["foreign_retention_amount"], 0.3, 2), 0
        )
        self.assertEqual(retention_lines_data[2]["aliquot"], 31)
        self.assertEqual(float_compare(retention_lines_data[2]["retention_amount"], 23.25, 2), 0)
        self.assertEqual(
            float_compare(retention_lines_data[2]["foreign_retention_amount"], 1.1625, 4), 0
        )
