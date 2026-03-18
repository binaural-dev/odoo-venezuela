import logging
from odoo.tests.common import Form
from odoo.tests import tagged
from odoo.exceptions import UserError, ValidationError
from odoo import Command, fields

from .test_common_purchase_international import TestCommonPurchaseInternational

_logger = logging.getLogger(__name__)


@tagged("igtf_providers_usd", "igtf_run", "-at_install", "post_install")
class TestIgtfPurchaseBook(TestCommonPurchaseInternational):

    def test01_payment_from_invoice(self,product_id=None):
        
        invoice_amount = float(2681.20)
        # expected_igtf = 60
        invoice = self._create_invoice_usd(invoice_amount,product_id)
        invoice.with_context(move_action_post_alert=True).action_post()
        _logger.info(f'MOVE:{invoice.name}')

    def get_purchases_book_wizard(self):

        with Form(self.env['wizard.accounting.reports']) as wiz_form:
            wiz_form.report = 'purchase'
            wiz_form.date_from = fields.Date.today()
            wiz_form.date_to = fields.Date.today()
            wizard = wiz_form.save()

        return wizard
    
    def test_purchase_book_line_fields_international_general(self):
        """Test that IGTF values are injected correctly into purchase book line."""
        # 🔹 1. Crear factura base usando tu flujo existente
        _logger.info(f'self.product_general_aliquot_purchase_internationa:{self.product_general_aliquot_purchase_international}')
        self.test01_payment_from_invoice(self.product_general_aliquot_purchase_international)
        invoice = self.env['account.move'].search([('move_type','=','in_invoice')], order="id desc", limit=1)

        _logger.info(f'NAME2:{invoice.name}')

        # 🔹 2. Crear wizard
        wizard = self.get_purchases_book_wizard()

        # 🔹 3. Obtener taxes como lo hace el reporte real
        taxes = wizard._determinate_amount_taxeds(invoice)

        # 🔹 4. Ejecutar método que estamos testeando
        line_fields = wizard._fields_purchase_book_line(invoice, taxes)

        _logger.info(f'LINE FIELDS:{line_fields}')

        self.assertIsNotNone(
        line_fields,
        "Para compras internacionales con impuestos, no debe devolver None"
        )

        # 🔸 Identidad del documento
        self.assertEqual(line_fields["_id"], invoice.id)
        self.assertEqual(line_fields["document_number"], invoice.name)

        # 🔸 Declaración de aduana
        self.assertEqual(
            line_fields["declaration_unique_of_customs"],
            invoice.declaration_unique_of_customs
        )

        # 🔸 Totales internacionales
        self.assertGreater(
            line_fields["total_purchases_international"],
            0,
            "El total de compras internacionales debe ser mayor a 0"
        )

        self.assertGreater(
            line_fields["total_purchases_iva_international"],
            0,
            "El total de compras internacionales con iva debe ser mayor a 0"
        )

        # 🔸 Base e impuesto IVA general internacional
        base_general = line_fields["tax_base_general_aliquot_international"]
        tax_general = line_fields["amount_general_aliquot_international"]

        self.assertGreater(
            base_general,
            0,
            "La base imponible general internacional debe ser mayor a 0"
        )

        self.assertAlmostEqual(
            tax_general,
            base_general * 0.16,
            places=2,
            msg="El IVA general internacional no corresponde al 16% de la base"
        )

        # 🔸 No deben existir otras alícuotas
        self.assertEqual(
            line_fields["tax_base_reduced_aliquot_international"], 0
        )
        self.assertEqual(
            line_fields["tax_base_extend_aliquot_international"], 0
        )

        # 🔸 Exento internacional no aplica
        self.assertEqual(
            line_fields["total_purchases_not_iva_international"], 0
        )

    def test_purchase_book_line_fields_international_extended(self):
        """Valida compra internacional con IVA extendido (32%)."""

        self.test01_payment_from_invoice(
            self.product_extend_aliquot_purchase_international
        )

        invoice = self.env['account.move'].search(
            [('move_type', '=', 'in_invoice')],
            order="id desc",
            limit=1
        )

        wizard = self.get_purchases_book_wizard()
        taxes = wizard._determinate_amount_taxeds(invoice)
        line_fields = wizard._fields_purchase_book_line(invoice, taxes)

        _logger.info(f'LINE FIELDS:{line_fields}')

        self.assertIsNotNone(line_fields)

        base_extend = line_fields["tax_base_extend_aliquot_international"]
        tax_extend = line_fields["amount_extend_aliquot_international"]

        self.assertGreater(
            base_extend,
            0,
            "La base extendida internacional debe ser mayor a 0"
        )

        self.assertAlmostEqual(
            tax_extend,
            base_extend * 0.32,
            places=2,
            msg="El IVA extendido internacional no corresponde al 32%"
        )

        self.assertGreater(
            line_fields["total_purchases_iva_international"], 0
        )

        self.assertEqual(
            line_fields["total_purchases_not_iva_international"], 0
        )

        # 🔸 No deben existir otras alícuotas
        self.assertEqual(
            line_fields["tax_base_general_aliquot_international"], 0
        )
        self.assertEqual(
            line_fields["tax_base_reduced_aliquot_international"], 0
        )

    def test_purchase_book_line_fields_international_reduced(self):
        """Valida compra internacional con IVA reducido (8%)."""

        self.test01_payment_from_invoice(
            self.product_reduced_aliquot_purchase_international
        )

        invoice = self.env['account.move'].search(
            [('move_type', '=', 'in_invoice')],
            order="id desc",
            limit=1
        )

        wizard = self.get_purchases_book_wizard()
        taxes = wizard._determinate_amount_taxeds(invoice)
        line_fields = wizard._fields_purchase_book_line(invoice, taxes)

        _logger.info(f'LINE FIELDS:{line_fields}')

        self.assertIsNotNone(line_fields)

        base_reduced = line_fields["tax_base_reduced_aliquot_international"]
        tax_reduced = line_fields["amount_reduced_aliquot_international"]

        self.assertGreater(
            base_reduced,
            0,
            "La base reducida internacional debe ser mayor a 0"
        )

        self.assertAlmostEqual(
            tax_reduced,
            base_reduced * 0.08,
            places=2,
            msg="El IVA reducido internacional no corresponde al 8%"
        )

        self.assertGreater(
            line_fields["total_purchases_iva_international"], 0
        )

        self.assertEqual(
            line_fields["total_purchases_not_iva_international"], 0
        )

        # 🔸 No deben existir otras alícuotas
        
        self.assertEqual(
            line_fields["tax_base_general_aliquot_international"], 0
        )
        self.assertEqual(
            line_fields["tax_base_extend_aliquot_international"], 0
        )

    def test_purchase_book_line_fields_international_exempt(self):
        """Valida compra internacional exenta de IVA."""

        self.test01_payment_from_invoice(
            self.product_exent_aliquot_purchase_international
        )

        invoice = self.env['account.move'].search(
            [('move_type', '=', 'in_invoice')],
            order="id desc",
            limit=1
        )

        wizard = self.get_purchases_book_wizard()
        taxes = wizard._determinate_amount_taxeds(invoice)
        line_fields = wizard._fields_purchase_book_line(invoice, taxes)

        _logger.info(f'LINE FIELDS:{line_fields}')

        self.assertIsNotNone(line_fields)

        # 🔸 Total internacional existe
        self.assertGreater(
            line_fields["total_purchases_international"], 0
        )

        # 🔸 Todo debe ser no IVA
        self.assertGreater(
            line_fields["total_purchases_not_iva_international"], 0
        )

        self.assertEqual(
            line_fields["total_purchases_iva_international"], 0
        )

        # 🔸 No debe existir base ni impuesto
        self.assertEqual(
            line_fields["tax_base_general_aliquot_international"], 0
        )
        self.assertEqual(
            line_fields["amount_general_aliquot_international"], 0
        )
        self.assertEqual(
            line_fields["amount_reduced_aliquot_international"], 0
        )
        self.assertEqual(
            line_fields["amount_extend_aliquot_international"], 0
        )


    def test_get_purchase_book_field_groups_international_full(self):
        """Verifica que los grupos y campos internacionales se generen completos."""
        company = self.company

        # 🔹 Asegurar que no se oculten campos internacionales
        company.write({
            "not_show_general_aliquot_purchase_international": False,
            "not_show_reduced_aliquot_purchase_international": False,
            "not_show_extend_aliquot_purchase_international": False,
            "not_show_total_purchases_international": False,
            "not_show_total_purchases_with_international_iva": False,
            "not_show_exempt_total_purchases": False,
        })

        wizard = self.get_purchases_book_wizard()
        groups = wizard._get_purchase_book_field_groups()

        headers = [group["header"] for group in groups]

        self.assertIn("COMPRAS INTERNACIONALES", headers)
        self.assertIn("TOTALES INTERNACIONALES", headers)

        international_group = next(
            g for g in groups if g["header"] == "COMPRAS INTERNACIONALES"
        )

        international_fields = [f["field"] for f in international_group["fields"]]

        # 🔸 Campos obligatorios
        self.assertIn("declaration_unique_of_customs", international_fields)
        self.assertIn("amount_import_international", international_fields)

        # 🔸 Alícuotas internacionales
        self.assertIn("tax_base_general_aliquot_international", international_fields)
        self.assertIn("amount_general_aliquot_international", international_fields)

        self.assertIn("tax_base_reduced_aliquot_international", international_fields)
        self.assertIn("amount_reduced_aliquot_international", international_fields)

        self.assertIn("tax_base_extend_aliquot_international", international_fields)
        self.assertIn("amount_extend_aliquot_international", international_fields)

        totals_group = next(
            g for g in groups if g["header"] == "TOTALES INTERNACIONALES"
        )

        total_fields = [f["field"] for f in totals_group["fields"]]

        self.assertIn("total_purchases_international", total_fields)
        self.assertIn("total_purchases_iva_international", total_fields)
        self.assertIn("total_purchases_not_iva_international", total_fields)

    def test_get_purchase_book_field_groups_hide_general_international(self):
        """No debe mostrar alícuota general internacional si está configurada para ocultarse."""
        company = self.env.company
        company.write({
            "not_show_general_aliquot_purchase_international": True,
            "not_show_reduced_aliquot_purchase_international": False,
            "not_show_extend_aliquot_purchase_international": False,
        })

        wizard = self.get_purchases_book_wizard()
        groups = wizard._get_purchase_book_field_groups()

        international_group = next(
            g for g in groups if g["header"] == "COMPRAS INTERNACIONALES"
        )

        fields = [f["field"] for f in international_group["fields"]]

        self.assertNotIn("tax_base_general_aliquot_international", fields)
        self.assertNotIn("amount_general_aliquot_international", fields)
        self.assertNotIn("general_aliquot", fields)

    def test_get_purchase_book_field_groups_only_exempt_international(self):
        """Solo debe mostrarse el total exento internacional."""
        company = self.env.company
        company.write({
            # 🔸 Ocultar todas las alícuotas
            "not_show_general_aliquot_purchase_international": True,
            "not_show_reduced_aliquot_purchase_international": True,
            "not_show_extend_aliquot_purchase_international": True,

            # 🔸 Ocultar totales con IVA
            "not_show_total_purchases_international": True,
            "not_show_total_purchases_with_international_iva": True,

            # 🔸 Mostrar solo exento
            "not_show_exempt_total_purchases": False,
        })

        wizard = self.get_purchases_book_wizard()
        groups = wizard._get_purchase_book_field_groups()

        headers = [g["header"] for g in groups]

        self.assertIn("TOTALES INTERNACIONALES", headers)
        self.assertNotIn("COMPRAS INTERNACIONALES", headers)

        totals_group = next(
            g for g in groups if g["header"] == "TOTALES INTERNACIONALES"
        )

        fields = [f["field"] for f in totals_group["fields"]]

        self.assertEqual(
            fields,
            ["total_purchases_not_iva_international"]
        )

    def test_get_purchase_book_field_groups_no_international(self):
        """No debe crearse ningún grupo internacional si todo está oculto."""
        company = self.env.company
        company.write({
            "not_show_general_aliquot_purchase_international": True,
            "not_show_reduced_aliquot_purchase_international": True,
            "not_show_extend_aliquot_purchase_international": True,
            "not_show_total_purchases_international": True,
            "not_show_total_purchases_with_international_iva": True,
            "not_show_exempt_total_purchases": True,
        })

        wizard = self.get_purchases_book_wizard()
        groups = wizard._get_purchase_book_field_groups()

        headers = [g["header"] for g in groups]

        self.assertNotIn("COMPRAS INTERNACIONALES", headers)
        self.assertNotIn("TOTALES INTERNACIONALES", headers)

    def _get_fields(self):
        wizard = self.get_purchases_book_wizard()
        fields = wizard.purchase_book_fields()
        return [f["field"] for f in fields]
    
    def test_purchase_book_fields_general_international(self):
        """Debe incluir los campos de IVA general internacional."""
        company = self.env.company
        company.write({
            "not_show_general_aliquot_purchase_international": False,
            "not_show_reduced_aliquot_purchase_international": True,
            "not_show_extend_aliquot_purchase_international": True,
        })

        fields = self._get_fields()

        self.assertIn("tax_base_general_aliquot_international", fields)
        self.assertIn("amount_general_aliquot_international", fields)

        self.assertNotIn("tax_base_reduced_aliquot_international", fields)
        self.assertNotIn("tax_base_extend_aliquot_international", fields)

    def test_purchase_book_fields_reduced_international(self):
        """Debe incluir los campos de IVA reducido internacional."""
        company = self.env.company
        company.write({
            "not_show_general_aliquot_purchase_international": True,
            "not_show_reduced_aliquot_purchase_international": False,
            "not_show_extend_aliquot_purchase_international": True,
        })

        fields = self._get_fields()

        self.assertIn("tax_base_reduced_aliquot_international", fields)
        self.assertIn("amount_reduced_aliquot_international", fields)

        self.assertNotIn("tax_base_general_aliquot_international", fields)
        self.assertNotIn("tax_base_extend_aliquot_international", fields)

    def test_purchase_book_fields_extend_international(self):
        """Debe incluir los campos de IVA extendido internacional."""
        company = self.env.company
        company.write({
            "not_show_general_aliquot_purchase_international": True,
            "not_show_reduced_aliquot_purchase_international": True,
            "not_show_extend_aliquot_purchase_international": False,
        })

        fields = self._get_fields()

        self.assertIn("tax_base_extend_aliquot_international", fields)
        self.assertIn("amount_extend_aliquot_international", fields)

        self.assertNotIn("tax_base_general_aliquot_international", fields)
        self.assertNotIn("tax_base_reduced_aliquot_international", fields)

    def test_purchase_book_fields_all_international(self):
        """Debe incluir todas las alícuotas internacionales."""
        company = self.env.company
        company.write({
            "not_show_general_aliquot_purchase_international": False,
            "not_show_reduced_aliquot_purchase_international": False,
            "not_show_extend_aliquot_purchase_international": False,
        })

        fields = self._get_fields()

        expected_fields = [
            "tax_base_general_aliquot_international",
            "amount_general_aliquot_international",
            "tax_base_reduced_aliquot_international",
            "amount_reduced_aliquot_international",
            "tax_base_extend_aliquot_international",
            "amount_extend_aliquot_international",
        ]

        for field in expected_fields:
            self.assertIn(field, fields)

