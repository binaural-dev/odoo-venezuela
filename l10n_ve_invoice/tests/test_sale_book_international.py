import logging
from odoo.tests.common import Form
from odoo.tests import tagged
from odoo.exceptions import UserError, ValidationError
from odoo import Command, fields

from .test_common_sale_international import TestCommonSaleInternational

_logger = logging.getLogger(__name__)

@tagged("l10n_ve_invoice", "-at_install", "post_install")
class TestSaleBook(TestCommonSaleInternational):

    def test01_payment_from_invoice(self,product_id=None,create_reversal=False):
        
        invoice_amount = float(2681.20)
        invoice = self._create_invoice_usd(invoice_amount,product_id)
        invoice.with_context(move_action_post_alert=True).action_post()

        if create_reversal:
            self._reverse_invoice_usd(invoice)

    def get_sales_book_wizard(self):

        with Form(self.env['wizard.accounting.reports']) as wiz_form:
            wiz_form.report = 'sale'
            wiz_form.date_from = fields.Date.today()
            wiz_form.date_to = fields.Date.today()
            wizard = wiz_form.save()

        return wizard
    
    def test_sale_book_line_fields_international_zero(self):
        self.test01_payment_from_invoice(self.product_zero_aliquot_sale_international)
        invoice = self.env['account.move'].search([('move_type','=','out_invoice')], order="id desc", limit=1)

        wizard = self.get_sales_book_wizard()

        taxes = wizard._determinate_amount_taxeds(invoice)

        line_fields = wizard._fields_sale_book_line(invoice, taxes)

        self.assertIsNotNone(
        line_fields,
            "Para ventas internacionales, no debe devolver None"
        )

        base_zero = line_fields["tax_base_zero_aliquot_international"]
        tax_zero = line_fields["amount_zero_aliquot_international"]

        self.assertEqual(
            base_zero,
            540181.36,
            "La base imponible general internacional debe ser mayor a 0"
        )

        self.assertEqual(
            tax_zero,
            base_zero * 0.00,
            msg="El IVA general internacional no corresponde al 00% de la base"
        )

        self.assertEqual(
            line_fields["tax_base_reduced_aliquot"], 0
        )
        self.assertEqual(
            line_fields["tax_base_extend_aliquot"], 0
        )
        self.assertEqual(
            line_fields["tax_base_general_aliquot"], 0
        )

        self.assertEqual(
            line_fields["amount_reduced_aliquot"], 0
        )
        self.assertEqual(
            line_fields["amount_extend_aliquot"], 0
        )
        self.assertEqual(
            line_fields["amount_general_aliquot"], 0
        )

    def test_sale_book_line_fields_international_zero_none(self):

        self.company.zero_aliquot_sale_international = False

        invoice_amount = float(2681.20)
        invoice = self._create_invoice_usd(invoice_amount,self.product_zero_aliquot_sale_international)

        invoice.with_context(move_action_post_alert=True).action_post()
        invoice = self.env['account.move'].search([('move_type','=','out_invoice')], order="id desc", limit=1)

        wizard = self.get_sales_book_wizard()

        taxes = wizard._determinate_amount_taxeds(invoice)

        line_fields = wizard._fields_sale_book_line(invoice, taxes)

        self.assertIsNone(
            line_fields,
            "Para ventas internacionales sin el impuesto cero configurado, debe devolver None"
        )

    def test_parse_sale_book_data_international(self):

        invoice_amount = float(2681.20)
        invoice = self._create_invoice_usd(invoice_amount,self.product_zero_aliquot_sale_international)

        invoice.with_context(move_action_post_alert=True).action_post()
        invoice = self.env['account.move'].search([('move_type','=','out_invoice')], order="id desc", limit=1)

        wizard = self.get_sales_book_wizard()

        data = wizard.parse_sale_book_data()

        self.assertTrue(data, "No se generaron líneas válidas")

        line = data[0]

        # ✅ 3. Validar estructura completa (campos clave reales)
        expected_keys = [
            "_id",
            "document_date",
            "accounting_date",
            "vat",
            "partner_name",
            "document_number",
            "move_type",
            "transaction_type",
            "correlative",
            "total_sales",
            "total_sales_iva",
            "total_sales_not_iva",
            "amount_zero_aliquot_international",
            "tax_base_zero_aliquot_international",
        ]

        for key in expected_keys:
            self.assertIn(key, line, f"Falta el campo {key}")

        _logger.info(f'AMOUNT ZERO ALIQUOT INTERNATIONAL:{line["amount_zero_aliquot_international"]}')

        self.assertEqual(
            line["amount_zero_aliquot_international"],
            0,
            "Debe haber monto en alícuota 0 internacional"
        )

        _logger.info(f'BASE ZERO ALIQUOT INTERNATIONAL:{line["tax_base_zero_aliquot_international"]}')

        self.assertEqual(
            line["tax_base_zero_aliquot_international"],
            540181.36,
            "Debe haber base imponible internacional"
        )

        # ✅ 7. No debería haber otros impuestos
        self.assertEqual(line["amount_general_aliquot"], 0)
        self.assertEqual(line["amount_reduced_aliquot"], 0)
        self.assertEqual(line["amount_extend_aliquot"], 0)

        # ✅ 8. Validar totales coherentes
        self.assertGreaterEqual(line["total_sales"], 0)

        self.assertAlmostEqual(
            line["total_sales"],
            line["total_sales_iva"] + line["total_sales_not_iva"],
            places=2,
            msg="Los totales no cuadran"
        )

    def test_sale_book_line_fields_international_zero(self):
        self.test01_payment_from_invoice(self.product_zero_aliquot_sale_international,True)
        invoice = self.env['account.move'].search([('move_type','=','out_refund')], order="id desc", limit=1)

        wizard = self.get_sales_book_wizard()

        taxes = wizard._determinate_amount_taxeds(invoice)

        line_fields = wizard._fields_sale_book_line(invoice, taxes)

        self.assertIsNotNone(
        line_fields,
            "Para ventas internacionales, no debe devolver None"
        )

        base_zero = line_fields["tax_base_zero_aliquot_international"]
        tax_zero = line_fields["amount_zero_aliquot_international"]

        self.assertEqual(
            base_zero,
            540181.36 * -1,
            "La base imponible general internacional debe ser mayor a 0"
        )

        self.assertEqual(
            tax_zero,
            base_zero * 0.00,
            msg="El IVA general internacional no corresponde al 00% de la base"
        )

        self.assertEqual(
            line_fields["tax_base_reduced_aliquot"], 0
        )
        self.assertEqual(
            line_fields["tax_base_extend_aliquot"], 0
        )
        self.assertEqual(
            line_fields["tax_base_general_aliquot"], 0
        )

        self.assertEqual(
            line_fields["amount_reduced_aliquot"], 0
        )
        self.assertEqual(
            line_fields["amount_extend_aliquot"], 0
        )
        self.assertEqual(
            line_fields["amount_general_aliquot"], 0
        )

    def test_get_sale_book_field_international_groups(self):
        """Validate sale international field group."""

        self.test01_payment_from_invoice(self.product_zero_aliquot_sale_international)

        wizard = self.get_sales_book_wizard()

        groups = wizard._get_sale_book_field_groups()

        group = next((g for g in groups if g.get("header") == "VENTAS INTERNACIONALES"), None)

        self.assertIsNotNone(group, "Debe existir grupo VENTAS INTERNACIONALES")
        field_names = [f["field"] for f in group["fields"]]
        self.assertIn("tax_base_zero_aliquot_international", field_names)
        self.assertIn("amount_zero_aliquot_international", field_names)

    def test_determinate_amount_taxeds_sale_international_zero(self):
        """
        Verifica que _determinate_amount_taxeds retorne correctamente
        tax_base_zero_aliquot_international y amount_zero_aliquot_international
        para una venta internacional con alícuota 0%.
        """

        self.test01_payment_from_invoice(
            self.product_zero_aliquot_sale_international
        )

        invoice = self.env['account.move'].search([('move_type','=','out_invoice')], order="id desc", limit=1)

        wizard = self.get_sales_book_wizard()

        taxes = wizard._determinate_amount_taxeds(invoice)

        self.assertIn(
            "tax_base_zero_aliquot_international",
            taxes,
            "Debe existir la base de IVA 0% internacional"
        )
        self.assertIn(
            "amount_zero_aliquot_international",
            taxes,
            "Debe existir el monto de IVA 0% internacional"
        )

        base_zero = taxes["tax_base_zero_aliquot_international"]
        amount_zero = taxes["amount_zero_aliquot_international"]

        # 🔹 5. Validar valores
        self.assertEqual(
            base_zero,
            540181.36,
            "La base imponible de IVA 0% internacional debe ser mayor a 0"
        )

        self.assertEqual(
            amount_zero,
            0.0,
            msg="El monto del IVA 0% internacional debe ser 0"
        )

    def test_determinate_resume_books_zero_aliquot_international(self):
        """
        Verifica que _determinate_resume_books calcule correctamente
        el resumen de IVA 0% internacional para ventas.
        """

        # 🔹 1. Crear y postear factura internacional con IVA 0%
        self.test01_payment_from_invoice(
            self.product_zero_aliquot_sale_international,
            True
        )

        invoices = self.env['account.move'].search([('move_type','in',['out_refund','out_invoice'])], order="id desc", limit=2)

        # 🔹 2. Crear wizard de libro de ventas
        wizard = self.get_sales_book_wizard()

        # 🔹 4. Ejecutar método bajo prueba
        resume = wizard._determinate_resume_books(
            invoices,
            tax_type="zero_aliquot_international"
        )

        # 🔹 5. Validaciones estructurales
        self.assertEqual(
            len(resume),
            4,
            "El resumen debe contener 4 valores"
        )

        base_moves, tax_moves, base_refunds, tax_refunds = resume

        # 🔹 6. Validaciones funcionales
        self.assertEqual(
            base_moves,
            540181.36,
            "La base imponible de IVA 0% internacional debe ser igual al de la factura realizada"
        )

        self.assertEqual(
            tax_moves,
            0.0,
            msg="El monto del IVA 0% internacional debe ser 0"
        )

        self.assertEqual(
            base_refunds,
            540181.36 * -1,
            "No deben existir notas de crédito para esta prueba"
        )

        self.assertEqual(
            tax_refunds,
            0.0,
            "No deben existir impuestos en notas de crédito"
        )