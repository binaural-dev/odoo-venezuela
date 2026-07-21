import logging
from odoo.tests import tagged , Form

from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_round
from odoo import Command, fields

from .test_common_purchase_book_igtf_usd_provider_formal import IGTFTestCommonPurchaseBook

_logger = logging.getLogger(__name__)


@tagged("igtf_providers_vef", "igtf_run", "-at_install", "post_install")
class TestIgtfPurchaseBook(IGTFTestCommonPurchaseBook):

    def test01_payment_from_invoice_with_igtf_journal(self,create_reversal=False):
        
        invoice_amount = float(2681.20)
        payment_amount = float(2000.00)
        expected_igtf = 60
        invoice = self._create_invoice_usd(invoice_amount)
        invoice.with_context(move_action_post_alert=True).action_post()
        
     
        cxc_credit_amount = payment_amount - expected_igtf 

        expected_residual = 741.2

        action_data = invoice.action_register_payment()
        
        with Form(
            self.env['account.payment.register'].with_context(
               action_data['context']  
            )
        ) as pay_form:
            
            pay_form.journal_id = self.bank_journal_usd
            pay_form.payment_date = fields.Date.today()
            pay_form.foreign_currency_id = self.currency_usd
            pay_form.save()
            pay_form.amount = payment_amount

        payment_register_wiz_2 = pay_form.record

        action = payment_register_wiz_2.action_create_payments()
        
        payment = self.env['account.payment'].browse(action.get('res_id'))
        payment_move = payment.move_id 
        
        
        self.assertTrue(payment_move, "Debe haberse creado el asiento de pago asociado al payment.")
        self.assertAlmostEqual(payment.igtf_amount, expected_igtf, 2, "El IGTF calculado debe ser $60.00.")
        
        self.assertEqual(
            invoice.payment_state, 
            'partial', 
            f"La factura debe estar en estado 'partial' (parcialmente pagada), estado actual: {invoice.payment_state}"
        )

        self.assertAlmostEqual(
            invoice.amount_residual, 
            expected_residual, 
            2, 
            f"El monto residual de la factura debe ser ${expected_residual}, pero es ${invoice.amount_residual}"
        )

        if create_reversal:
            self._reverse_invoice_usd(invoice)

    def get_purchases_book_wizard(self):

        with Form(self.env['wizard.accounting.reports']) as wiz_form:
            wiz_form.report = 'purchase'
            wiz_form.date_from = fields.Date.today()
            wiz_form.date_to = fields.Date.today()
            wizard = wiz_form.save()

        return wizard
    
    def test_purchase_book_fields_includes_igtf_columns(self):
        """Ensure IGTF columns are added to purchase book fields."""

        self.test01_payment_from_invoice_with_igtf_journal()

        wizard = self.get_purchases_book_wizard()

        purchase_book_fields = wizard.purchase_book_fields()

        # --- 1️⃣ Validar que sea lista ---
        self.assertIsInstance(purchase_book_fields, list, "purchase_book_fields debe retornar una lista")

        # Convertimos a dict por nombre de field para buscar fácil
        fields_by_fieldname = {f["field"]: f for f in purchase_book_fields if "field" in f}

        # --- 2️⃣ Verificar existencia de campos ---
        # self.assertIn("bi_igtf", fields_by_fieldname, "No se agregó el campo bi_igtf")
        self.assertIn("igtf", fields_by_fieldname, "No se agregó el campo igtf")

        # --- 3️⃣ Validar estructura bi_igtf ---
        # bi_igtf = fields_by_fieldname["bi_igtf"]
        # self.assertEqual(bi_igtf["name"], "Bi igtf")
        # self.assertEqual(bi_igtf["format"], "number")

        # --- 4️⃣ Validar estructura igtf ---
        igtf = fields_by_fieldname["igtf"]
        self.assertEqual(igtf["name"], "IGTF")
        self.assertEqual(igtf["format"], "number")

    def test_purchase_book_line_fields_with_igtf(self):
        """Test that IGTF values are injected correctly into purchase book line."""
        # 🔹 1. Crear factura base usando tu flujo existente
        self.test01_payment_from_invoice_with_igtf_journal()
        invoice = self.env['account.move'].search([('move_type','=','in_invoice')], order="id desc", limit=1)

        # 🔹 2. Crear wizard
        wizard = self.get_purchases_book_wizard()

        # 🔹 3. Obtener taxes como lo hace el reporte real
        taxes = wizard._determinate_amount_taxeds(invoice)

        # 🔹 4. Ejecutar método que estamos testeando
        line_fields = wizard._fields_purchase_book_line(invoice, taxes)

        # 🔹 5. Validar que super no se perdió
        self.assertIsInstance(line_fields, dict)

        # 🔹 6. Validar que IGTF fue inyectado
        # self.assertIn("bi_igtf", line_fields)
        self.assertIn("igtf", line_fields)

        # 🔹 7. Validar valores según sistema de moneda
        if wizard.currency_system:
            # self.assertEqual(line_fields["bi_igtf"], invoice.bi_igtf)
            self.assertEqual(float_round(line_fields["igtf"],2), float_round(invoice.alter_bi_igtf,2))

    #Se dejan este test comentado debido a que el super de _get_purchase_book_field_groups 
    # aun no se encuentra en el ambiente donde se subiran a priori estas pruebas unitarias

    def test_get_purchase_book_field_groups_igtf_visibility(self):
        """Validate IGTF field group behavior based on company flags."""

        company = self.env.company

        self.test01_payment_from_invoice_with_igtf_journal()

        # Helper para crear wizard
        def _get_groups():
            with Form(self.env['wizard.accounting.reports']) as wiz_form:
                wiz_form.report = 'purchase'
                wiz_form.date_from = fields.Date.today()
                wiz_form.date_to = fields.Date.today()
                wizard = wiz_form.save()
            return wizard._get_purchase_book_field_groups()

        # ---------------------------
        # 🟢 Caso 1: mostrar ambos
        # ---------------------------
        # company.not_show_bi_igtf_purchase_order = False
        company.not_show_igtf_purchase_order = False

        groups = _get_groups()
        igtf_group = next((g for g in groups if g.get("header") == "IGTF"), None)

        self.assertIsNotNone(igtf_group, "Debe existir grupo IGTF")
        field_names = [f["field"] for f in igtf_group["fields"]]
        # self.assertIn("bi_igtf", field_names)
        self.assertIn("igtf", field_names)

        # ---------------------------
        # 🟡 Caso 2: ocultar BI IGTF
        # ---------------------------
        # company.not_show_bi_igtf_purchase_order = True
        company.not_show_igtf_purchase_order = False

        groups = _get_groups()
        igtf_group = next((g for g in groups if g.get("header") == "IGTF"), None)

        self.assertIsNotNone(igtf_group)
        field_names = [f["field"] for f in igtf_group["fields"]]
        # self.assertNotIn("bi_igtf", field_names)
        self.assertIn("igtf", field_names)

        # ---------------------------
        # 🟠 Caso 3: ocultar IGTF monto
        # ---------------------------
        # company.not_show_bi_igtf_purchase_order = False
        company.not_show_igtf_purchase_order = True

        groups = _get_groups()
        igtf_group = next((g for g in groups if g.get("header") == "IGTF"), None)

        self.assertIsNone(igtf_group)

        # ---------------------------
        # 🔴 Caso 4: ocultar ambos
        # ---------------------------
        # company.not_show_bi_igtf_purchase_order = True
        company.not_show_igtf_purchase_order = True

        groups = _get_groups()
        igtf_group = next((g for g in groups if g.get("header") == "IGTF"), None)

        self.assertIsNone(igtf_group, "No debe existir grupo IGTF si ambos están ocultos")
