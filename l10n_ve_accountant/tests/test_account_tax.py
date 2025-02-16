from odoo.tests import Form
from .common import BinauralAccountTestInvoicingCommon
from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo import Command, fields
from datetime import timedelta


import logging
_logger = logging.getLogger(__name__)


@tagged("account_tax", "post_install", "-at_install")
class TestAccountTax(BinauralAccountTestInvoicingCommon):
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
                "foreign_inverse_rate": 25.0,
                "manually_set_rate": True,
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

        expected_tax_0_amount = 0
        expected_tax_1_amount = 219.88
        expected_tax_2_amount = 646.66
        expected_tax_3_amount = 811.9

        tax_0_amount = 0
        tax_1_amount = 0
        tax_2_amount = 0
        tax_3_amount = 0

        for tax in invoice.tax_totals["groups_by_foreign_subtotal"]["Subtotal"]:
            if tax["tax_group_id"] == self.tax0.tax_group_id.id:
                self.assertEqual(tax["tax_group_amount"], expected_tax_0_amount)
                tax_0_amount = tax["tax_group_amount"]
            if tax["tax_group_id"] == self.tax1.tax_group_id.id:
                self.assertEqual(tax["tax_group_amount"], expected_tax_1_amount)
                tax_1_amount = tax["tax_group_amount"]
            if tax["tax_group_id"] == self.tax2.tax_group_id.id:
                self.assertEqual(tax["tax_group_amount"], expected_tax_2_amount)
                tax_2_amount = tax["tax_group_amount"]
            if tax["tax_group_id"] == self.tax3.tax_group_id.id:
                self.assertEqual(tax["tax_group_amount"], expected_tax_3_amount)
                tax_3_amount = tax["tax_group_amount"]

        for line in invoice.line_ids.filtered(lambda line: line.display_type == "tax"):
            if line.tax_line_id == self.tax0:
                self.assertEqual(abs(line.foreign_balance), tax_0_amount)
            if line.tax_line_id == self.tax1:
                self.assertEqual(abs(line.foreign_balance), tax_1_amount)
            if line.tax_line_id == self.tax2:
                self.assertEqual(abs(line.foreign_balance), tax_2_amount)
            if line.tax_line_id == self.tax3:
                self.assertEqual(abs(line.foreign_balance), tax_3_amount)

        payment_term = sum(
            invoice.line_ids.filtered(lambda line: line.display_type == "payment_term").mapped("foreign_balance")
        )

        self.assertEqual(invoice.tax_totals["foreign_amount_untaxed"], 49587.75)
        self.assertEqual(invoice.tax_totals["foreign_amount_total"], 51266.19)
        self.assertEqual(payment_term, invoice.tax_totals["foreign_amount_total"])

    def test_03(self):
        """
        Test taxes in foreign currency
        """
        self.change_tax_included()
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

        expected_tax_0_amount = 0
        expected_tax_1_amount = 189.55
        expected_tax_2_amount = 598.76
        expected_tax_3_amount = 619.76

        tax_0_amount = 0
        tax_1_amount = 0
        tax_2_amount = 0
        tax_3_amount = 0

        for tax in invoice.tax_totals["groups_by_foreign_subtotal"]["Subtotal"]:
            if tax["tax_group_id"] == self.tax0.tax_group_id.id:
                self.assertEqual(tax["tax_group_amount"], expected_tax_0_amount)
                tax_0_amount = tax["tax_group_amount"]
            if tax["tax_group_id"] == self.tax1.tax_group_id.id:
                self.assertEqual(tax["tax_group_amount"], expected_tax_1_amount)
                tax_1_amount = tax["tax_group_amount"]
            if tax["tax_group_id"] == self.tax2.tax_group_id.id:
                self.assertEqual(tax["tax_group_amount"], expected_tax_2_amount)
                tax_2_amount = tax["tax_group_amount"]
            if tax["tax_group_id"] == self.tax3.tax_group_id.id:
                self.assertEqual(tax["tax_group_amount"], expected_tax_3_amount)
                tax_3_amount = tax["tax_group_amount"]

        for line in invoice.line_ids.filtered(lambda line: line.display_type == "tax"):
            if line.tax_line_id == self.tax0:
                self.assertEqual(abs(line.foreign_balance), tax_0_amount)
            if line.tax_line_id == self.tax1:
                self.assertEqual(abs(line.foreign_balance), tax_1_amount)
            if line.tax_line_id == self.tax2:
                self.assertEqual(abs(line.foreign_balance), tax_2_amount)
            if line.tax_line_id == self.tax3:
                self.assertEqual(abs(line.foreign_balance), tax_3_amount)

        payment_term = sum(
            invoice.line_ids.filtered(lambda line: line.display_type == "payment_term").mapped("foreign_balance")
        )

        self.assertEqual(invoice.tax_totals["foreign_amount_untaxed"], 48179.68)
        self.assertEqual(invoice.tax_totals["foreign_amount_total"], 49587.75)
        self.assertEqual(payment_term, invoice.tax_totals["foreign_amount_total"])
