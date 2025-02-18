from odoo.tests import tagged
from odoo import Command
from .common import AccountRetentionTestCommon
from odoo.tools import float_compare
from odoo.exceptions import UserError


@tagged("post_install", "-at_install", "islr_retention", "base_vef_retention")
class TestIslrRetentionBs(AccountRetentionTestCommon):
    """
    Test that the retention islr line data is computed correctly for a given invoice with base.VEF

    Requires:
        partner: partner with payment_conecept_id
    """

    def test_islr_account_line_compute_vef_base(self):
        """
        """
        invoice = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.partner_a.id,
                "journal_id": self.journal_sale.id,
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
                ],
                "retention_islr_line_ids": [
                    Command.create(
                        {
                            "name": "Retencion ISLR",
                            "payment_concept_id": self.env.ref("l10n_ve_payment_extension.payment_concept_one_binaural_payment_extension").id,
                            
                        }
                    ),
                ],
            }
        )
        for ret_line in invoice.retention_islr_line_ids:
            # Check that the retention line data is computed correctly.
            self.assertEqual(ret_line.related_percentage_tax_base, 100)
            self.assertEqual(ret_line.related_percentage_fees, 5)
            
        invoice.action_post()
        self.assertEqual(invoice.state, "posted")
    

    def test_create_islr_retention(self):
        """
        """
        retention = self.env["account.retention"].create(
            {   
                "type_retention": "islr",
                "type": "in_invoice",
                "company_id": self.company_data["company"].id,
                "partner_id": self.partner_b.id,
                "retention_line_ids": [
                    Command.create(
                        {
                            # "name": "Retencion ISLR",
                            "move_id": self.account_move.id,
                            "payment_concept_id": self.env.ref("l10n_ve_payment_extension.payment_concept_one_binaural_payment_extension").id,
                        }
                    ),
                ],
            }
        )
        for ret_line in retention.retention_line_ids:
            # Check that the retention line data is computed correctly.
            self.assertEqual(ret_line.related_percentage_tax_base, 100)
            self.assertEqual(ret_line.related_percentage_fees, 5)

        retention.action_post()
        self.assertEqual(retention.state, "emitted")
