import logging
import datetime
from odoo.tests import TransactionCase, tagged
from odoo import fields, Command
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
                "foreign_currency_id": self.currency_vef.id,
            }
        )



        self.tax_iva16 = self.env['account.tax'].create({
            'name': 'IVA 16%',
            'amount': 16,
            'amount_type': 'percent',
            'type_tax_use': 'sale',
        })

        self.product = self.env['product.product'].create({
            'name': 'Producto Prueba',
            'type': 'service',
            'list_price': 100,
            'barcode': '123456789',
            'taxes_id': [(6, 0, [self.tax_iva16.id])],
        })
        
        self.partner_a = self.env['res.partner'].create({
            'name': 'Test Partner A',
            'customer_rank': 1,
        })
        
        self.company_data = {
            'company': self.env['res.company'].create({
                'name': 'Test Company',
                'currency_id': self.env.ref('base.VEF').id,
                'confirm_invoice_with_current_date': False,
            }),
        }
        sequence = self.env['ir.sequence'].create({
            'name': 'Secuencia Factura',
            'code': 'account.move',
            'prefix': 'INV/',
            'padding': 8,
            "number_next_actual": 2,
        })
        refund_sequence = self.env['ir.sequence'].create({
            'name': 'nota de credito',
            'code': '',
            'prefix': 'NC/',
            'padding': 8,
            "number_next_actual": 2,
        })

        self.journal = self.env['account.journal'].create({
            'name': 'Diario de Ventas',
            'code': 'VEN',
            'type': 'sale',
            'sequence_id': sequence.id,
            "refund_sequence_id": refund_sequence.id,
            'company_id': self.env.company.id,
        })

      
    def _create_invoice(
            self, 
            products, 
            move_type="out_invoice", 
            reversed_entry_id=None, 
            debit_origin_id=None, 
            ref = "Test Invoice",
            foreign_rate=38,
            foreign_inverse_rate=38,
            invoice_date=None
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

        name = self.journal.sequence_id.next_by_id()

        if move_type == "out_refund" and reversed_entry_id:
            name = self.journal.refund_sequence_id.next_by_id()

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
            "invoice_date": fields.Date.today(),
            "invoice_date_display": fields.Date.today(),
            "journal_id": self.journal.id,
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

        invoice.action_post()
        return invoice

    def test_check_price_in_zero_rejects_bare_negative_subtotal_line(self):
        """`_check_price_in_zero` (`@api.constrains('invoice_line_ids')`) rejects
        any invoice line with `price_subtotal <= 0` that isn't a recognized
        discount line (`_get_discount_lines()`). Relocated from
        `l10n_ve_accountant/tests/test_multi_currency_rounding.py::test_31_mixed_sign_lines_both_rounding_modes`
        (PR #1344/#1417 investigation): that assertion tested THIS module's own
        constraint and can't be guaranteed to run in a test DB where only
        `l10n_ve_accountant` is installed (confirmed via PR #1417, a diff
        isolated to that module -- it failed with this exact assertion)."""
        with self.assertRaises(ValidationError):
            self._create_invoice([
                {
                    "product_id": self.product.id,
                    "price_unit": 11.16,
                    "tax_ids": [(6, 0, [self.tax_iva16.id])],
                },
                {
                    "product_id": self.product.id,
                    "price_unit": -4.16,
                    "tax_ids": [(6, 0, [self.tax_iva16.id])],
                },
            ])

    def test_check_price_in_zero_rejects_negative_line_sharing_tax_with_positive_line(self):
        """Same constraint as above, different amounts -- relocated from
        `l10n_ve_accountant/tests/test_real_portion.py::test_34i_negative_line_blocked_by_existing_invoice_constraint`
        (PR #1344/#1417 investigation), kept as a separate case since it
        documents the concrete shape (100/-20 split) that test's original
        author found relevant."""
        with self.assertRaises(ValidationError):
            self._create_invoice([
                {
                    "product_id": self.product.id,
                    "price_unit": 100.0,
                    "tax_ids": [(6, 0, [self.tax_iva16.id])],
                },
                {
                    "product_id": self.product.id,
                    "price_unit": -20.0,
                    "tax_ids": [(6, 0, [self.tax_iva16.id])],
                },
            ])

   