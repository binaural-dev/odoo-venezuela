from odoo.tests import Form
from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo import Command, fields
from datetime import timedelta


@tagged("account_tax", "post_install", "-at_install")
class TestAccountTax(TransactionCase):
    def setUp(self):
        super().setUp()
        self.journal_sale = self.env["account.journal"].search([("type", "=", "sale")])[0]
        tax_group_obj = self.env["account.tax.group"]
        tax_obj = self.env["account.tax"]

        self.partner = self.env["res.partner"].create(
            {
                "name": "Test Partner",
                "email": "",
                "vat": "27436422",
            }
        )

        self.tax_group = tax_group_obj.create({"name": "IVA SALES", "sequence": 1})

        self.tax0 = tax_obj.create(
            {
                "name": "EXENTO",
                "type_tax_use": "sale",
                "amount_type": "percent",
                "amount": "0.00",
                "description": "EXENTO",
                "tax_group_id": self.tax_group.id,
            }
        )

        self.tax1 = tax_obj.create(
            {
                "name": "IVA 16",
                "type_tax_use": "sale",
                "amount_type": "percent",
                "amount": "16.00",
                "description": "IVA 16",
                "tax_group_id": self.tax_group.id,
            }
        )
        self.tax2 = tax_obj.create(
            {
                "name": "IVA 8",
                "type_tax_use": "sale",
                "amount_type": "percent",
                "amount": "8.00",
                "description": "IVA 8",
                "tax_group_id": self.tax_group.id,
            }
        )

        self.product1 = self.env["product.product"].create(
            {
                "name": "Test Product 16",
                "type": "service",
                "list_price": 19.49,
                "taxes_id": self.tax1,
            }
        )

        self.product2 = self.env["product.product"].create(
            {
                "name": "Test Product 8",
                "type": "service",
                "list_price": 18.99,
                "taxes_id": self.tax2,
            }
        )

        self.product3 = self.env["product.product"].create(
            {
                "name": "Test Product Exento",
                "type": "service",
                "list_price": 7.23,
                "taxes_id": self.tax0,
            }
        )

        base_vef = self.env.ref("base.VEF")

        base_vef.write(
            {
                "rate_ids": [
                    Command.create(
                        {
                            "name": fields.Date.today() - timedelta(days=1),
                            "company_rate": 23.46,
                        }
                    ),
                ]
            }
        )

    def test01(self):
        """
        Check if the foreign currency is configurated
        """
        self.env.company.currency_foreign_id = False
        with self.assertRaises(ValidationError):

            invoice = self.env["account.move"].create(
                {
                    "partner_id": self.partner.id,
                    "date": fields.Date.today(),
                    "move_type": "out_invoice",
                    "state": "draft",
                    "company_id": self.env.company.id,
                    "currency_id": self.env.company.currency_id.id,
                    "journal_id": self.journal_sale.id,
                }
            )
            invoice._compute_tax_totals()

    def test_02(self):
        """
        Test taxes in foreign currency
        """
        self.env.company.currency_foreign_id = self.env.ref("base.VEF")
        invoice = self.env["account.move"].create(
            {
                "partner_id": self.partner.id,
                "date": fields.Date.today(),
                "move_type": "out_invoice",
                "state": "draft",
                "company_id": self.env.company.id,
                "currency_id": self.env.company.currency_id.id,
                "journal_id": self.journal_sale.id,
            }
        )

        invoice.invoice_line_ids = [
            Command.create(
                {
                    "product_id": self.product1.id,
                    "quantity": 48,
                }
            ),
            Command.create(
                {
                    "product_id": self.product3.id,
                    "quantity": 5,
                }
            ),
            Command.create(
                {
                    "product_id": self.product2.id,
                    "quantity": 4,
                }
            ),
            Command.create(
                {
                    "product_id": self.product1.id,
                    "quantity": 8,
                }
            ),
            Command.create(
                {
                    "product_id": self.product3.id,
                    "quantity": 12,
                }
            ),
            Command.create(
                {
                    "product_id": self.product2.id,
                    "quantity": 1,
                }
            ),
            Command.create(
                {
                    "product_id": self.product1.id,
                    "quantity": 34,
                }
            ),
            Command.create(
                {
                    "product_id": self.product2.id,
                    "quantity": 23,
                }
            ),
        ]

        self.assertEqual(invoice.tax_totals["foreign_amount_total"], 64091.62)
