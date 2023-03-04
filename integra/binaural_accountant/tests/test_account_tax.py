from odoo.tests import Form
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo import Command, fields
from datetime import timedelta


@tagged("account_tax", "post_install", "-at_install")
class TestAccountTax(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls, chart_template_ref=None):
        """
        l10n_ve is required to run this test
        """
        super().setUpClass(chart_template_ref="l10n_ve.ve_chart_template_amd")
        cls.env.company.write(
            {
                "currency_id": cls.env.ref("base.USD").id,
                "currency_foreign_id": cls.env.ref("base.VEF").id,
            }
        )
        tax_group_obj = cls.env["account.tax.group"]
        tax_obj = cls.env["account.tax"]

        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Test Partner",
                "email": "",
                "vat": "27436422",
            }
        )

        cls.tax_group = tax_group_obj.create({"name": "IVA SALES", "sequence": 1})

        cls.tax0 = tax_obj.create(
            {
                "name": "EXENTO",
                "type_tax_use": "sale",
                "amount_type": "percent",
                "amount": "0.00",
                "description": "EXENTO",
                "tax_group_id": cls.tax_group.id,
            }
        )

        cls.tax1 = tax_obj.create(
            {
                "name": "IVA 16",
                "type_tax_use": "sale",
                "amount_type": "percent",
                "amount": "16.00",
                "description": "IVA 16",
                "tax_group_id": cls.tax_group.id,
            }
        )

        cls.tax2 = tax_obj.create(
            {
                "name": "IVA 8",
                "type_tax_use": "sale",
                "amount_type": "percent",
                "amount": "8.00",
                "description": "IVA 8",
                "tax_group_id": cls.tax_group.id,
            }
        )

        cls.tax3 = tax_obj.create(
            {
                "name": "IVA 31",
                "type_tax_use": "sale",
                "amount_type": "percent",
                "amount": "31.00",
                "description": "IVA 31",
                "tax_group_id": cls.tax_group.id,
            }
        )

        base_vef = cls.env.ref("base.VEF")

        base_vef.write(
            {
                "rate_ids": [
                    Command.create(
                        {
                            "name": fields.Date.today() - timedelta(days=1),
                            "company_rate": 25,
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
            lines = [
                (9.97, self.tax1),
                (123.33, self.tax2),
                (99.98, self.tax3),
                (0.45, self.tax0),
                (1500.00, self.tax0),
                (45, self.tax1),
                (200, self.tax2),
                (4.78, self.tax3),
            ]
            invoice = self._create_document_for_tax_totals_test(lines)
            invoice._compute_tax_totals()

    def _create_document_for_tax_totals_test(self, lines_data):
        """Creates and returns a new record of a model defining a tax_totals
        field and using the related widget.
        By default, this function creates an invoice, but it is overridden in sale
        and purchase to create respectively a sale.order or a purchase.order. This way,
        we can test the invoice_tax_totals from both these models in the same way as
        account.move's.
        :param lines_data: a list of tuple (amount, taxes), where amount is a base amount,
                           and taxes a recordset of account.tax objects corresponding
                           to the taxes to apply on this amount. Each element of the list
                           corresponds to a line of the document (invoice line, PO line, SO line).
        """
        invoice_lines_vals = [
            (
                0,
                0,
                {
                    "name": "line",
                    "display_type": "product",
                    "account_id": self.company_data["default_account_revenue"].id,
                    "price_unit": amount,
                    "tax_ids": [(6, 0, taxes.ids)],
                },
            )
            for amount, taxes in lines_data
        ]

        return self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner_a.id,
                "invoice_date": fields.Date.today() - timedelta(days=1),
                "foreign_currency_id": self.env.ref("base.VEF").id,
                "foreign_rate": 25.0,
                "invoice_line_ids": invoice_lines_vals,
            }
        )

    def test_02(self):
        """
        Test taxes in foreign currency
        """
        lines = [
            (9.97, self.tax1),
            (123.33, self.tax2),
            (99.98, self.tax3),
            (0.45, self.tax0),
            (1500.00, self.tax0),
            (45, self.tax1),
            (200, self.tax2),
            (4.78, self.tax3),
        ]
        invoice = self._create_document_for_tax_totals_test(lines)
        self.assertEqual(invoice.tax_totals["foreign_amount_total"], 51266.19)
