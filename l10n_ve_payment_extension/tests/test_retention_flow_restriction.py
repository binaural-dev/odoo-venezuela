# -*- coding: utf-8 -*-

from odoo.tests import TransactionCase, tagged
from odoo.exceptions import UserError

@tagged('post_install', '-at_install', 'l10n_ve_retention_flow_restriction')
class TestRetentionFlowRestriction(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super(TestRetentionFlowRestriction, cls).setUpClass()
        cls.company = cls.env.user.company_id
        # Restringe env.companies a una sola compañía: con varias compañías
        # demo permitidas al usuario, los defaults de producto (taxes_id)
        # toman impuestos de TODAS las compañías permitidas y disparan un
        # falso "Fiscal inconsistencies... Has 2 taxes assigned".
        cls.env = cls.env(context=dict(cls.env.context, allowed_company_ids=[cls.company.id]))
        cls.company.currency_id = cls.env.ref('base.VEF')
        cls.company.foreign_currency_id = cls.env.ref("base.USD")

        cls.env.company.currency_id = cls.env.ref('base.VEF')
        cls.env.company.foreign_currency_id = cls.env.ref('base.USD')

        cls.partner = cls.env["res.partner"].create({"name": "Test Partner Retention Flow Restriction"})
        cls.product = cls.env["product.product"].create({"name": "Test Service Flow Restriction", "type": "service"})
        cls.journal = cls.env["account.journal"].search(
            [("company_id", "=", cls.env.company.id), ("type", "=", "purchase")], limit=1
        )

    def test_create_retention_on_draft_invoice(self):
        """Test that we cannot create a third-party retention on a draft invoice via the retention model."""
        invoice = self.env["account.move"].create({
            "partner_id": self.partner.id,
            "move_type": "in_invoice",
            "journal_id": self.journal.id,
            "invoice_line_ids": [(0, 0, {"product_id": self.product.id, "quantity": 1, "price_unit": 100.0})],
        })
        self.assertEqual(invoice.state, "draft")

        with self.assertRaises(UserError) as e:
            self.env["account.retention"].create([{
                "type_retention": "iva",
                "type": "in_invoice",
                "partner_id": self.partner.id,
                "is_third_party_retention": True,
                "retention_line_ids": [(0, 0, {
                    "name": "Test Line",
                    "move_id": invoice.id,
                    "invoice_total": 116.0,
                    "invoice_amount": 100.0,
                    "iva_amount": 16.0,
                    "retention_amount": 12.0
                })]
            }])
        
        self.assertIn("You cannot create retentions for a draft or cancelled invoice.", str(e.exception))

    def test_write_retention_on_draft_invoice(self):
        """Test that we cannot modify a third-party retention onto a draft invoice."""
        # Create a posted invoice first to bypass creation restriction
        posted_invoice = self.env["account.move"].create({
            "partner_id": self.partner.id,
            "move_type": "in_invoice",
            "journal_id": self.journal.id,
            "invoice_line_ids": [(0, 0, {"product_id": self.product.id, "quantity": 1, "price_unit": 100.0})],
        })
        posted_invoice.action_post()
        
        retention = self.env["account.retention"].create([{
            "type_retention": "iva",
            "type": "in_invoice",
            "partner_id": self.partner.id,
            "is_third_party_retention": True,
            "retention_line_ids": [(0, 0, {
                "name": "Test Line",
                "move_id": posted_invoice.id,
                "invoice_total": 116.0,
                "invoice_amount": 100.0,
                "iva_amount": 16.0,
                "retention_amount": 12.0
            })]
        }])

        draft_invoice = self.env["account.move"].create({
            "partner_id": self.partner.id,
            "move_type": "in_invoice",
            "journal_id": self.journal.id,
            "invoice_line_ids": [(0, 0, {"product_id": self.product.id, "quantity": 1, "price_unit": 100.0})],
        })
        
        with self.assertRaises(UserError) as e:
            retention.write({
                "retention_line_ids": [(0, 0, {
                    "name": "Test Line 2",
                    "move_id": draft_invoice.id,
                    "invoice_total": 116.0,
                    "invoice_amount": 100.0,
                    "iva_amount": 16.0,
                    "retention_amount": 12.0
                })]
            })
            
        self.assertIn("You cannot modify retentions for a draft or cancelled invoice.", str(e.exception))
