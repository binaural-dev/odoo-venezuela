import logging
import datetime
from datetime import timedelta
from odoo.tests import TransactionCase, tagged
from odoo import fields, Command
from unittest.mock import patch
from datetime import date as real_date
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "l10n_ve_invoice")
class TestAccountMove(TransactionCase):
    """Tests for invoice posting behaviour regarding the invoice date."""

    def setUp(self):
        super(TestAccountMove, self).setUp()
        self.currency_usd = self.env.ref("base.USD")
        self.currency_vef = self.env.ref("base.VEF")
        self.company = self.env.ref("base.main_company")
        self.company.write(
            {
                "currency_id": self.currency_usd.id,
                "currency_foreign_id": self.currency_vef.id,
            }
        )

        self.tax_iva16 = self.env["account.tax"].create(
            {
                "name": "IVA 16%",
                "amount": 16,
                "amount_type": "percent",
                "type_tax_use": "sale",
            }
        )

        self.product = self.env["product.product"].create(
            {
                "name": "Producto Prueba",
                "type": "service",
                "list_price": 100,
                "barcode": "123456789",
                "taxes_id": [(6, 0, [self.tax_iva16.id])],
            }
        )

        self.partner_a = self.env["res.partner"].create(
            {
                "name": "Test Partner A",
                "customer_rank": 1,
            }
        )

        self.company_data = {
            "company": self.env["res.company"].create(
                {
                    "name": "Test Company",
                    "currency_id": self.env.ref("base.VEF").id,
                }
            ),
        }
        sequence = self.env["ir.sequence"].create(
            {
                "name": "Secuencia Factura",
                "code": "account.move",
                "prefix": "INV/",
                "padding": 8,
                "number_next_actual": 2,
            }
        )
        refund_sequence = self.env["ir.sequence"].create(
            {
                "name": "nota de credito",
                "code": "",
                "prefix": "NC/",
                "padding": 8,
                "number_next_actual": 2,
            }
        )

        self.sales_journal = self.env["account.journal"].create(
            {
                "name": "Diario de Ventas",
                "code": "VEN",
                "type": "sale",
                "sequence_id": sequence.id,
                "refund_sequence_id": refund_sequence.id,
                "company_id": self.env.company.id,
            }
        )

        self.purchase_journal = self.env["account.journal"].create(
            {
                "name": "Diario de compras",
                "code": "COM",
                "type": "purchase",
                "sequence_id": sequence.id,
                "refund_sequence_id": refund_sequence.id,
                "company_id": self.env.company.id,
            }
        )

    def _create_invoice(
        self,
        products,
        move_type="out_invoice",
        reversed_entry_id=None,
        debit_origin_id=None,
        ref="Test Invoice",
        foreign_rate=38,
        foreign_inverse_rate=38,
        invoice_date=None,
        date=None,
        journal=None,
    ):
        """Helper function to create an invoice with given parameters.
        Args:
            products (list): List of dictionaries with product details.
            foreign_rate (float): Foreign exchange rate.
            foreign_inverse_rate (float): Inverse foreign exchange rate.
        """
        invoice_lines = [
            Command.create(
                {
                    "product_id": product["product_id"],
                    "quantity": product.get("quantity", 1),
                    "price_unit": product["price_unit"],
                    "tax_ids": product.get("tax_ids", []),
                }
            )
            for product in products
        ]

        journal = self.sales_journal

        if move_type == "in_invoice":
            journal = self.purchase_journal

        name = journal.sequence_id.next_by_id()

        if move_type == "out_refund" and reversed_entry_id:
            name = journal.refund_sequence_id.next_by_id()

        if move_type == "out_invoice" and debit_origin_id:
            name = self.debit_journal.sequence_id.next_by_id()

        invoice_vals = {
            "name": name,
            "move_type": move_type,
            "partner_id": self.partner_a.id,
            "foreign_currency_id": self.currency_vef.id,
            "currency_id": self.currency_usd.id,
            "state": "draft",
            "foreign_rate": foreign_rate,
            "foreign_inverse_rate": foreign_inverse_rate,
            "manually_set_rate": True,
            "invoice_line_ids": invoice_lines,
            "invoice_date": invoice_date or fields.Date.today(),
            "date": date or fields.Date.today(),
            "journal_id": journal.id,
            "correlative": 1,
        }

        # Solo para notas de crédito
        if move_type == "out_refund" and reversed_entry_id:
            invoice_vals["reversed_entry_id"] = reversed_entry_id.id
            invoice_vals["ref"] = ref

        if move_type == "out_invoice" and debit_origin_id:
            invoice_vals["debit_origin_id"] = debit_origin_id.id
            invoice_vals["ref"] = ref

        invoice = self.env["account.move"].create(invoice_vals)

        return invoice

    def _assert_entry_in_period(self, invoice_date, today_date, taxpayer_type, expected):
        """Helper to create a move, patch today's date and assert entry_in_period."""
        self.company.write({"taxpayer_type": taxpayer_type})

        move = self._create_invoice(
            products=[
                {
                    "product_id": self.product.id,
                    "price_unit": 1,
                    "tax_ids": [self.tax_iva16.id],
                }
            ],
            move_type="out_refund",
            invoice_date=invoice_date,
            journal=self.purchase_journal,
        )

        class FakeDate(real_date):
            @classmethod
            def today(cls):
                return today_date

        with patch('odoo.addons.l10n_ve_invoice.models.account_move.date', FakeDate):
            move._compute_entry_in_period()

        if expected:
            self.assertTrue(move.entry_in_period, f"Falló: Se esperaba True para hoy {today_date} e invoice {invoice_date}")
        else:
            self.assertFalse(move.entry_in_period, f"Falló: Se esperaba False para hoy {today_date} e invoice {invoice_date}")

    def test_01_create_in_invoice(self):
        
        invoice = self._create_invoice(
            products=[
                {
                    "product_id": self.product.id,
                    "price_unit": 1,
                    "tax_ids": [self.tax_iva16.id],
                }
            ],
            move_type="in_invoice",
            journal=self.purchase_journal,
        )
        invoice.action_post()
        self.assertTrue(
            invoice.state == "posted", "The invoice should be posted after creation."
        )
        _logger.info("test_01_create_in_invoice --- successfully.")

    # def test_02_error_create_in_invoice(self):
    #     invoice = self._create_invoice(
    #         products=[
    #             {
    #                 "product_id": self.product.id,
    #                 "price_unit": 1,
    #                 "tax_ids": [self.tax_iva16.id],
    #             }
    #         ],
    #         move_type="in_invoice",
    #         invoice_date=fields.Date.today(),
    #         date=fields.Date.today() - timedelta(days=1),
    #         journal=self.purchase_journal,
    #     )
    #     with self.assertRaises(UserError) as e:
    #         invoice.action_post()
    #     _logger.info("Error creating invoice: %s", e.exception)

    #     exception = "The accounting date cannot be earlier than the invoice date."

    #     self.assertEqual(
    #         str(e.exception),
    #         exception,
    #         f"The error message should indicate that: {exception}",
    #     )
    #     _logger.info("test_02_error_create_in_invoice --- successfully.")

    def test_03_normal_taxpayer_invoice_in_period(self):
        """Regular taxpayer: invoice from the same month before the deadline -> True"""
        today = real_date.today()
        invoice_date = today.replace(day=1)
        today_date = today.replace(day=2)
        
        self._assert_entry_in_period(invoice_date, today_date, 'formal', True)

    def test_04_special_taxpayer_before_15_in_period(self):
        """Special taxpayer, today < 15 -> deadline period day 15 -> invoice day 10 considered IN period (True)"""
        today = real_date.today()
        invoice_date = today.replace(day=10)
        today_date = today.replace(day=12)
        
        self._assert_entry_in_period(invoice_date, today_date, 'special', True)

    def test_05_special_taxpayer_after_15_out_of_period(self):
        """Special taxpayer, today >= 15 -> last day of the deadline period -> invoice date <15 remains OUT period (False)"""
        today = real_date.today()
        invoice_date = today.replace(day=10)
        today_date = today.replace(day=20)
        
        self._assert_entry_in_period(invoice_date, today_date, 'special', False)

    def test_06_invoice_different_month_not_in_period(self):
        """Invoice from previous month -> outside the fiscal period"""
        today = real_date.today()

        first_day_this_month = today.replace(day=1)
        last_day_prev_month = first_day_this_month - timedelta(days=1)
        
        invoice_date = last_day_prev_month
        today_date = today
        
        self._assert_entry_in_period(invoice_date, today_date, False, False)
