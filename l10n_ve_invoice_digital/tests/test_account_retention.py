from odoo.tests import TransactionCase, tagged, Form
from datetime import date
from odoo.exceptions import UserError, ValidationError
from odoo import Command, fields
from unittest.mock import patch, MagicMock
import logging

_logger = logging.getLogger(__name__)

@tagged("post_install", "-at_install", "l10n_ve_invoice_digital", "retention_digital") 
class TestAccumulatedRate(TransactionCase):
    def setUp(self):
        super().setUp()
        self.currency_vef = self.env.ref("base.VEF")
        self.currency_usd = self.env.ref("base.USD")
        self.company = self.env.ref("base.main_company")
        self.env.user.tz = "America/Caracas"
        iva_sequence = self.env["ir.sequence"].create({
            "name": "Secuencia de iva para proveedores",
            "code": "payment.retention.iva",
            "prefix": "",
            "padding": 8,
            "number_next_actual": 1,
        })

        bank_account = self.env["account.account"].search([("account_type", "=", "liquidity")], limit=1)
        transitory_account = self.env["account.account"].search([("account_type", "=", "other")], limit=1)
        profit_account = self.env["account.account"].search([("account_type", "=", "income")], limit=1)
        loss_account = self.env["account.account"].search([("account_type", "=", "expense")], limit=1)

        self.iva_journal = self.env["account.journal"].create({
            "name": "Retenciones IVA",
            "code": "RETIVA",
            "type": "bank",
            "sequence_id": iva_sequence.id,
            "company_id": self.env.company.id,
            "bank_account_id": bank_account.id,
            "default_account_id": transitory_account.id,
            "profit_account_id": profit_account.id,
            "loss_account_id": loss_account.id,
        })

        self.payment_method_inbound = self.env['account.payment.method'].create({
                'name': 'Manual',
                'code': 12,
                'payment_type': 'inbound'
        })

        self.payment_method_outbound = self.env['account.payment.method'].create({
            'name': 'Manual',
            'code': 12,
            'payment_type': 'outbound'
            })

        self.islr_supplier_retention_journal = self.env["account.journal"].create({
            "name": "Retenciones ISLR PROVEEDOR",
            "code": "RTISLR",
            "type": "bank",
            "sequence_id": iva_sequence.id,
            "company_id": self.env.company.id,
            "bank_account_id": bank_account.id,
            "default_account_id": transitory_account.id,
            "profit_account_id": profit_account.id,
            "loss_account_id": loss_account.id,
            "inbound_payment_method_line_ids": [Command.create({
                'payment_method_id':self.payment_method_inbound.id, 
                'name': 'Manual'
            })],
            "outbound_payment_method_line_ids": [Command.create({
                'payment_method_id': self.payment_method_outbound.id, 
                'name': 'Manual'
            })],
        })

        self.company.write({
            "currency_id": self.currency_usd.id,
            "currency_foreign_id": self.currency_vef.id,
            "iva_supplier_retention_journal_id": self.iva_journal.id,
            "islr_supplier_retention_journal_id": self.islr_supplier_retention_journal.id,
            "url_tfhka": "https://api.tfhka.com",
            "token_auth_tfhka": "token_fake",
            "invoice_digital_tfhka": True,
        })

        self.tax_group_iva16 = self.env["account.tax.group"].create({"name": "IVA 16%"})

        self.tax_iva16 = self.env["account.tax"].create({
            "name": "IVA 16%",
            "amount": 16,
            "amount_type": "percent",
            "type_tax_use": "purchase",
            "tax_group_id": self.tax_group_iva16.id,
        })

        self.product = self.env["product.product"].create({
            "name": "Producto Prueba",
            "type": "service",
            "list_price": 100,
            "barcode": "123456789",
            "purchase_ok": True,
            "supplier_taxes_id": [(6, 0, [self.tax_iva16.id])],
            "taxes_id": [(6, 0, [self.tax_iva16.id])],
        })

        self.payment_concept = self.env["payment.concept"].create({
            "name": "Test Payment Concept",
            "status": True,
        })

        self.line_payment_concept = self.env["payment.concept.line"].create({
            'type_person_id': self.env.ref('l10n_ve_payment_extension.type_person_l10n_ve_payment_extension').id,
            'payment_concept_id': self.payment_concept.id,
            'code': 52,
            'percentage_tax_base': 100,
            'tariff_id': self.env.ref('l10n_ve_payment_extension.fees_retention_data_percentage_one_l10n_ve_payment_extension').id,
            'pay_from': 0.13,
        })

        self.payment_concept.write({"line_payment_concept_ids": [(6, 0, [self.line_payment_concept.id])]})

        self.partner_a = self.env["res.partner"].create({
            "name": "Test Partner A",
            "customer_rank": 1,
            'vat': 'J12345678',
            "country_id": self.env.ref('base.ve').id,
            'phone': '04141234567',
            'email': 'cliente@prueba.com',
            'street': 'Calle Falsa 123',
            "type_person_id": self.env.ref('l10n_ve_payment_extension.type_person_l10n_ve_payment_extension').id,
            "withholding_type_id": self.env["account.withholding.type"]
            .search([("name", "=", "75%")], limit=1)
            .id,
        })

        sequence = self.env["ir.sequence"].create({
            "name": "Secuencia Factura",
            "code": "account.move",
            "prefix": "INV/",
            "padding": 8,
            "number_next_actual": 1,
        })
        refund_sequence = self.env["ir.sequence"].create({
            "name": "nota de credito",
            "code": "",
            "prefix": "NC/",
            "padding": 8,
            "number_next_actual": 1,
        })

        self.journal = self.env["account.journal"].create({
            "name": "Diario de Ventas",
            "code": "VEN",
            "type": "purchase",
            "sequence_id": sequence.id,
            "refund_sequence_id": refund_sequence.id,
            "company_id": self.env.company.id,
        })

    def _create_invoice(self):
        invoice = self.env["account.move"].create({
            "move_type": "in_invoice",
            "partner_id": self.partner_a.id,
            "journal_id": self.journal.id,
            "invoice_date": fields.Date.today(),
            "invoice_line_ids": [
                (
                    0,
                    0,
                    {
                        "product_id": self.product.id,
                        "quantity": 2,
                        "price_unit": 100,
                        "tax_ids": [(6, 0, [self.tax_iva16.id])],
                        "price_subtotal": 200,
                        "price_total": 232,
                        "foreign_rate": 2.0,
                        "foreign_inverse_rate": 2.0,
                        "foreign_price": 200,
                        "foreign_subtotal": 400,
                        "foreign_price_total": 464,
                    },
                ),
            ],
        })

        return invoice

    def _create_retention(self, type_retention, invoice):
        today = fields.Date.today()

        with Form(self.env["account.retention"].with_context(default_type="in_invoice", default_type_retention=type_retention)) as retention_form:
            retention_form.partner_id = self.partner_a
            retention_form.date_accounting = today

        retention = retention_form.save()

        with Form(retention) as retention_form_edit:
            with retention_form_edit.retention_line_ids.new() as line:
                line.move_id = invoice
                line.payment_concept_id = self.payment_concept

        retention = retention_form_edit.save()

        return retention

    # def _create_subsidiary(self, name="Sucursal prueba"):
    #     analytic_plan = self.env['account.analytic.plan'].create({
    #         'name': 'Plan para pruebas',
    #     })

    #     return self.env['account.analytic.account'].create({
    #         'name': name,
    #         'is_subsidiary': True,
    #         'company_id': self.env.company.id,
    #         'plan_id': analytic_plan.id,
    #         'code': "002",
    #     })

    def mock_api(company, endpoint_key, payload, *args, **kwargs):

        if endpoint_key == "emision":
            return {"codigo": "200", "resultado": {"numeroControl": "00-00000001"}}
        elif endpoint_key == "ultimo_documento":
            return {"codigo": "200", "numeroDocumento": 1}
        elif endpoint_key == "consulta_numeraciones":
            return {"numeraciones": 
                [
                    {"serie": "NO APLICA", "hasta": "100000", "correlativo": "01"},
                    {"serie": "A", "hasta": "110000","correlativo": "100052"},
                ],
                "codigo": "200",
                "mensaje": "Consulta realizada exitosamente",
            }
    
    @patch('odoo.addons.l10n_ve_invoice_digital.services.tfhka_client.TfhkaApiClient._request', side_effect=mock_api)
    def test_01_create_retention_iva_success(self, mock_call):
        account_move = self._create_invoice()
        account_move.action_post()
        retention_iva = self._create_retention("iva", account_move) 
        retention_iva.action_post()
        _logger.info(f"Estado de la retencion: {retention_iva.state}")

        retention_iva.with_context(account_retention_alert=True).generate_document_digital()
        self.assertEqual(retention_iva.is_digitalized, True)

    @patch('odoo.addons.l10n_ve_invoice_digital.services.tfhka_client.TfhkaApiClient._request', side_effect=mock_api)
    def test_02_create_retention_islr_success(self, mock_call):

        account_move = self._create_invoice()
        account_move.action_post()
        retention_islr = self._create_retention("islr", account_move)
        retention_islr.action_post()

        retention_islr.with_context(account_retention_alert=True).generate_document_digital()
        self.assertEqual(retention_islr.is_digitalized, True)

    # DetallesRetencion debe usar los nombres de campo de la spec TFHKA (Tabla 24):
    # "retenido" (monto retenido, obligatorio) y "porcentaje" (alicuota), no
    # "retenidoIVA"/"porcentajeIVA" para esos valores. "retenidoIVA" sigue
    # existiendo pero para el monto de retención especial
    # (related_percentage_tax_base). No usa API.
    def test_retention_details_field_names(self):
        account_move = self._create_invoice()
        account_move.action_post()
        retention_iva = self._create_retention("iva", account_move)
        retention_iva.action_post()

        details = self.env['tfhka.retention.service']._prepare_detail_lines(retention_iva, "05")
        self.assertTrue(details, "get_retention_details debe devolver al menos una línea")
        detail = details[0]
        self.assertIn("retenido", detail)
        self.assertIn("porcentaje", detail)
        self.assertIn("retenidoIVA", detail)
        self.assertNotIn("porcentajeIVA", detail)

    # Anulacion de retencion via wizard (endpoint /Anular)
    @patch('odoo.addons.l10n_ve_invoice_digital.services.tfhka_client.TfhkaApiClient._request', side_effect=mock_api)
    def test_annul_retention_wizard(self, mock_call):
        account_move = self._create_invoice()
        account_move.action_post()
        retention = self._create_retention("iva", account_move)
        retention.action_post()
        retention.with_context(account_retention_alert=True).generate_document_digital()
        self.assertTrue(retention.is_digitalized)

        wizard = self.env['tfhka.annul.wizard'].create({
            'retention_id': retention.id,
            'reason': 'Error de emision',
        })
        wizard.action_confirm()
        self.assertTrue(retention.annulled_tfhka)

    # API de TFHKA para consultar numeraciones
    @patch('odoo.addons.l10n_ve_invoice_digital.services.tfhka_client.TfhkaApiClient._request')
    def test_03_query_numbering_success(self, mock_call):

        mock_call.return_value = {
            "numeraciones": [
                {
                    "titulo": "NUMERACIÓN DE 1 A 100000",
                    "serie": "NO APLICA",
                    "tipoDocumento": "TODOS",
                    "prefijo": "00",
                    "desde": "1",
                    "hasta": "100000",
                    "correlativo": "645",
                    "estado": "True"
                }
            ],
            "codigo": "200",
            "mensaje": "Consulta realizada exitosamente"
        }

        account_move = self._create_invoice()
        account_move.action_post()
        retention = self._create_retention("iva", account_move)
        retention.action_post()

        series = ""
        response = self.env['tfhka.api.client'].query_numbering(retention.company_id, series)
        _logger.info("Response from query_numbering: %s", response)

        # Verificamos que la respuesta fue la esperada
        self.assertEqual(response, None)

    # API de TFHKA para obtener el último número de documento
    @patch('odoo.addons.l10n_ve_invoice_digital.services.tfhka_client.TfhkaApiClient._request')
    def test_04_get_last_document_number_success(self, mock_call):
        mock_call.return_value = {
            "numeroDocumento": 126,
            "codigo": "200",
            "mensaje": "Consulta realizada exitosamente"
        }

        account_move = self._create_invoice()
        account_move.action_post()
        retention = self._create_retention("iva", account_move)
        retention.action_post()

        document_type = "02"
        response = self.env['tfhka.api.client'].get_last_document_number(retention.company_id, document_type)
        _logger.info("Response from get_last_document_number: %s", response)

        # Verificamos que la respuesta fue la esperada
        self.assertEqual(response, 126)

    # API de TFHKA para generar documento digital (factura, nota de crédito, nota de débito)
    @patch('odoo.addons.l10n_ve_invoice_digital.services.tfhka_client.TfhkaApiClient._request')
    def test_05_generate_document_data_success(self, mock_call):
        mock_call.return_value = {
            "resultado": {
                "imprentaDigital": "THE FACTORY HKA VENEZUELA, C.A.",
                "autorizado": "Imprenta Digital Autorizada mediante Providencia SENIAT/INTI/XXXXXXX de fecha 09/09/2022",
                "serie": "",
                "tipoDocumento": "01",
                "numeroDocumento": "329",
                "numeroControl": "00-00000646",
                "fechaAsignacion": "03/02/2023",
                "horaAsignacion": "01:26:30 PM",
                "fechaAsignacionNumeroControl": "10/06/2025",
                "horaAsignacionNumeroControl": "02:49:11 PM",
                "rangoAsignado": "Nros. de Control desde el 00-00000001 hasta 00-00100000",
                "urlConsulta": "https://democonsulta.thefactoryhka.com.ve/?doc=4veMdK7d7zPkGconw/7fyG8qQxFGrk9KhWAr1hCY8D7lq3an6kwmqgXyxFca+9EI"
            },
            "codigo": "200",
            "mensaje": "Documento procesado correctamente"
        }

        account_move = self._create_invoice()
        account_move.action_post()
        retention = self._create_retention("iva", account_move)
        retention.action_post()

        document_type = "02"
        document_number = "12345678"
        validation_sequence = True
        response = self.env['tfhka.retention.service'].generate_document_data(retention, document_number, document_type, validation_sequence)
        _logger.info("Response from generate_document_data: %s", response)

        # Verificamos que la respuesta fue la esperada
        self.assertEqual(response, None)

    # Validacion de secuencia entre la API y Odoo
    @patch('odoo.addons.l10n_ve_invoice_digital.services.tfhka_client.TfhkaApiClient._request', side_effect=mock_api)
    def test_06_generate_document_digital_sequence_error(self, mock_call):
        self.company.write({"sequence_validation_tfhka": True,})

        account_move = self._create_invoice()
        account_move.action_post()
        retention = self._create_retention("iva", account_move)
        retention.action_post()

        res = retention.with_context(account_retention_alert=True).generate_document_digital()

        _logger.info(res)

        self.assertIsNone(res) 
        # self.assertEqual(retention.is_digitalized, True)

        _logger.info("Test passed: Sequence validation error raised as expected.")

    # API de TFHKA para consultar numeraciones con número de serie agotado
    @patch('odoo.addons.l10n_ve_invoice_digital.services.tfhka_client.TfhkaApiClient._request')
    def test_07_query_numbering_numbering_sold_out_error(self, mock_call):

        mock_call.return_value = {
            "numeraciones": [
                {
                    "titulo": "NUMERACIÓN DE 1 A 100000",
                    "serie": "NO APLICA",
                    "tipoDocumento": "TODOS",
                    "prefijo": "00",
                    "desde": "1",
                    "hasta": "100000",
                    "correlativo": "100000",
                    "estado": "True"
                }
            ],
            "codigo": "200",
            "mensaje": "Consulta realizada exitosamente"
        }

        account_move = self._create_invoice()
        account_move.action_post()
        retention = self._create_retention("iva", account_move)
        retention.action_post()

        series = ""
        with self.assertRaises(UserError) as e:
            self.env['tfhka.api.client'].query_numbering(retention.company_id, series)
            _logger.error(e.exception)
        
        _logger.info("Test passed: Numbering sold out error raised as expected.")

    # Llamada a la API de TFHKA URL vacía
    def test_08_call_tfhka_api_URL_error(self):
        self.company.write({"url_tfhka": "",})

        account_move = self._create_invoice()
        account_move.action_post()
        retention = self._create_retention("iva", account_move)
        retention.action_post()

        endpoint_key = "emision"
        payload={
            "serie": "",
            "tipoDocumento": "",
            "prefix": ""
        }
        with self.assertRaises(UserError) as e:
            self.env['tfhka.api.client']._request(retention.company_id, endpoint_key, payload)
            _logger.error(e.exception)

        _logger.info("Test passed: URL for TFHKA is empty, UserError raised as expected.")

    # Llamada a la API de TFHKA Token vacío
    def test_09_call_tfhka_api_token_error(self):
        self.company.write({"token_auth_tfhka": ""})

        account_move = self._create_invoice()
        account_move.action_post()
        retention = self._create_retention("iva", account_move)
        retention.action_post()

        endpoint_key = "emision"
        payload={
            "serie": "",
            "tipoDocumento": "",
            "prefix": ""
        }
        with self.assertRaises(UserError) as e:
            self.env['tfhka.api.client']._request(retention.company_id, endpoint_key, payload)
            _logger.error(e.exception)

        _logger.info("Test passed: Token for TFHKA is empty, UserError raised as expected.")

    # Llamada a la API de TFHKA con error 400
    @patch('requests.post')
    def test_10_call_tfhka_api_status_code_400_error(self, mock_call):
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_call.return_value = mock_response

        account_move = self._create_invoice()
        account_move.action_post()
        retention = self._create_retention("iva", account_move)
        retention.action_post()

        endpoint_key = "emision"
        payload={
            "serie": "",
            "tipoDocumento": "",
            "prefix": ""
        }
        with self.assertRaises(UserError) as e:
            self.env['tfhka.api.client']._request(retention.company_id, endpoint_key, payload)
            _logger.error(e.exception)

        _logger.info("Test passed: code 400 error, UserError raised as expected.")

    # Llamada a la API de TFHKA con error 200 pero con mensaje de error
    @patch('requests.post')
    def test_11_call_tfhka_api_status_code_200_error(self, mock_call):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "codigo": "400",
            "mensaje": "Error en la petición"
        }
        mock_call.return_value = mock_response

        account_move = self._create_invoice()
        account_move.action_post()
        retention = self._create_retention("iva", account_move)
        retention.action_post()

        endpoint_key = "emision"
        payload={
            "serie": "",
            "tipoDocumento": "",
            "prefix": ""
        }
        with self.assertRaises(UserError) as e:
            self.env['tfhka.api.client']._request(retention.company_id, endpoint_key, payload)
            _logger.error(e.exception)

        _logger.info("Test passed: code 200 error, UserError raised as expected.")

    def test_12_generate_document_digital_already_digitized(self):
        account_move = self._create_invoice()
        account_move.action_post()
        retention = self._create_retention("iva", account_move)
        retention.action_post()
        retention.is_digitalized = True
        with self.assertRaises(UserError):
            retention.generate_document_digital()

    def test_13_get_total_retention_base_vef(self):
        vef_company = self.env["res.company"].create({
            "name": "Compañía VEF Test",
            "currency_id": self.env.ref("base.VEF").id,
        })
        vef_company.currency_id = self.env.ref("base.VEF")
        account_move = self._create_invoice()
        account_move.action_post()
        retention = self._create_retention("iva", account_move)
        retention.action_post()
        retention.base_currency_is_vef = True
        total = self.env['tfhka.retention.service']._prepare_totals(retention, "05")
        self.assertIn("totalBaseImponible", total)

    def test_14_get_retention_details_islr(self):
        account_move = self._create_invoice()
        account_move.action_post()
        retention = self._create_retention("islr", account_move)
        retention.action_post()
        details = self.env['tfhka.retention.service']._prepare_detail_lines(retention, "06")
        self.assertTrue(len(details) > 0)
        self.assertIn("CodigoConcepto", details[0])

    def test_15_call_tfhka_api_undefined_endpoint(self):
        account_move = self._create_invoice()
        account_move.action_post()
        retention = self._create_retention("iva", account_move)
        retention.action_post()
        with self.assertRaises(UserError):
            self.env['tfhka.api.client']._request(retention.company_id, "no_existe", {})

    @patch('requests.post')
    def test_16_call_tfhka_api_401_refresh(self, mock_post):
        self.company.write({
            "username_tfhka": "u",
            "password_tfhka": "p",
            "url_tfhka": "https://api.tfhka.com",
            "token_auth_tfhka": "old",
            "invoice_digital_tfhka": True,
            "sequence_validation_tfhka": True,
        })
        def side_effect(url, *args, **kwargs):
            resp = MagicMock()
            if "/Autenticacion" in url:
                resp.status_code = 200
                resp.json.return_value = {
                    "codigo": 200,
                    "mensaje": "OK",
                    "token": "refreshed_token",
                    "expiracion": "2025-12-31T23:59:59",
                }
            else:
                if not hasattr(side_effect, 'emision_calls'):
                    side_effect.emision_calls = 0
                side_effect.emision_calls += 1
                if side_effect.emision_calls == 1:
                    resp.status_code = 401
                    resp.text = "Unauthorized"
                else:
                    resp.status_code = 200
                    resp.json.return_value = {"codigo": "200", "mensaje": "OK", "resultado": {"numeroControl": "00-00000001"}}
            return resp
        mock_post.side_effect = side_effect
        account_move = self._create_invoice()
        account_move.action_post()
        retention = self._create_retention("iva", account_move)
        retention.action_post()
        result = self.env['tfhka.api.client']._request(retention.company_id, "emision", {})
        self.assertEqual(result["codigo"], "200")

    def test_17_get_subject_retention_missing_vat(self):
        account_move = self._create_invoice()
        account_move.action_post()
        retention = self._create_retention("iva", account_move)
        retention.action_post()
        retention.partner_id.vat = False
        with self.assertRaises(UserError):
            self.env['tfhka.retention.service']._get_fiscal_party(retention)

    def test_18_get_subject_retention_missing_country(self):
        account_move = self._create_invoice()
        account_move.action_post()
        retention = self._create_retention("iva", account_move)
        retention.action_post()
        retention.partner_id.country_id = False
        with self.assertRaises(UserError):
            self.env['tfhka.retention.service']._get_fiscal_party(retention)

    def test_19_get_subject_retention_missing_phone(self):
        account_move = self._create_invoice()
        account_move.action_post()
        retention = self._create_retention("iva", account_move)
        retention.action_post()
        retention.partner_id.mobile = False
        retention.partner_id.phone = False
        with self.assertRaises(UserError):
            self.env['tfhka.retention.service']._get_fiscal_party(retention)

    def test_20_get_subject_retention_missing_email(self):
        account_move = self._create_invoice()
        account_move.action_post()
        retention = self._create_retention("iva", account_move)
        retention.action_post()
        retention.partner_id.email = False
        with self.assertRaises(UserError):
            self.env['tfhka.retention.service']._get_fiscal_party(retention)

    def test_21_compute_visibility_button(self):
        account_move = self._create_invoice()
        account_move.action_post()
        retention = self._create_retention("iva", account_move)
        retention.action_post()
        retention._compute_visibility_button()
        self.assertFalse(retention.show_digital_retention_iva)
        self.assertFalse(retention.show_digital_retention_islr)

    def test_23_generate_document_data_with_validation_sequence(self):
        account_move = self._create_invoice()
        account_move.action_post()
        retention = self._create_retention("iva", account_move)
        retention.action_post()
        # Simular generación con validation_sequence=True
        with patch('odoo.addons.l10n_ve_invoice_digital.services.tfhka_client.TfhkaApiClient._request') as mock_call:
            mock_call.return_value = {
                "resultado": {"numeroControl": "00-00000001"},
                "codigo": "200",
                "mensaje": "OK",
            }
            self.env['tfhka.retention.service'].generate_document_data(retention, "R00001", "05", True)
            self.assertTrue(retention.is_digitalized)
            messages = retention.message_ids.mapped('body')
            self.assertTrue(any("Warning accepted" in str(m) for m in messages))

    def test_24_get_last_document_number_zero(self):
        account_move = self._create_invoice()
        account_move.action_post()
        retention = self._create_retention("iva", account_move)
        retention.action_post()
        with patch('odoo.addons.l10n_ve_invoice_digital.services.tfhka_client.TfhkaApiClient._request') as mock_call:
            mock_call.return_value = 0
            result = self.env['tfhka.api.client'].get_last_document_number(retention.company_id, "05")
            self.assertEqual(result, 0)

    def test_25_query_numbering_no_series(self):
        account_move = self._create_invoice()
        account_move.action_post()
        retention = self._create_retention("iva", account_move)
        retention.action_post()
        with patch('odoo.addons.l10n_ve_invoice_digital.services.tfhka_client.TfhkaApiClient._request') as mock_call:
            mock_call.return_value = {
                "numeraciones": [],
                "codigo": "200",
                "mensaje": "OK",
            }
            with self.assertRaises(UserError):
                self.env['tfhka.api.client'].query_numbering(retention.company_id)

    def test_26_get_retention_details_islr_without_code(self):
        account_move = self._create_invoice()
        account_move.action_post()
        retention = self._create_retention("islr", account_move)
        retention.action_post()
        for line in retention.retention_line_ids:
            line.code = False
        details = self.env['tfhka.retention.service']._prepare_detail_lines(retention, "06")
        self.assertTrue(len(details) > 0)
        self.assertNotIn("CodigoConcepto", details[0])

    # ------------------------------------------------------------------
    # Cobertura adicional: account_retention.py / tfhka_retention_service.py
    # ------------------------------------------------------------------

    def test_27_send_retention_company_disabled(self):
        self.company.invoice_digital_tfhka = False
        account_move = self._create_invoice()
        account_move.action_post()
        retention = self._create_retention("iva", account_move)
        retention.action_post()
        result = self.env['tfhka.retention.service'].send_retention(retention)
        self.assertIsNone(result)

    def test_28_send_retention_document_number_long_string(self):
        account_move = self._create_invoice()
        account_move.action_post()
        retention = self._create_retention("iva", account_move)
        retention.action_post()
        with patch(
            'odoo.addons.l10n_ve_invoice_digital.services.tfhka_client.TfhkaApiClient.get_last_document_number',
            return_value="12345678",
        ):
            with patch(
                'odoo.addons.l10n_ve_invoice_digital.services.tfhka_client.TfhkaApiClient.query_numbering',
                return_value=None,
            ):
                with patch(
                    'odoo.addons.l10n_ve_invoice_digital.services.tfhka_client.TfhkaApiClient.emit',
                    return_value={"codigo": "200", "resultado": {"numeroControl": "00-00000001"}},
                ):
                    result = retention.with_context(account_retention_alert=True).generate_document_digital()
        # documentNumberStr con longitud > 6: se toma el resto desde la posicion 6 + 1
        self.assertIsInstance(result, type(None))

    @patch('odoo.addons.l10n_ve_invoice_digital.services.tfhka_client.TfhkaApiClient._request', side_effect=mock_api)
    def test_29_send_retention_sequence_mismatch_opens_wizard(self, mock_call):
        account_move = self._create_invoice()
        account_move.action_post()
        retention = self._create_retention("iva", account_move)
        retention.action_post()
        # Sin account_retention_alert en el contexto: si la secuencia de Odoo
        # no coincide con la de The Factory, se abre el wizard de alerta.
        result = retention.generate_document_digital()
        self.assertIsInstance(result, dict)
        self.assertEqual(result.get('res_model'), 'account.retention.alert.wizard')

    def test_30_annul_retention_not_digitalized_raises(self):
        account_move = self._create_invoice()
        account_move.action_post()
        retention = self._create_retention("iva", account_move)
        retention.action_post()
        with self.assertRaises(UserError):
            self.env['tfhka.retention.service'].annul_retention(retention, "Motivo de prueba")

    @patch('odoo.addons.l10n_ve_invoice_digital.services.tfhka_client.TfhkaApiClient._request', side_effect=mock_api)
    def test_31_annul_retention_already_annulled_raises(self, mock_call):
        account_move = self._create_invoice()
        account_move.action_post()
        retention = self._create_retention("iva", account_move)
        retention.action_post()
        retention.with_context(account_retention_alert=True).generate_document_digital()
        self.env['tfhka.retention.service'].annul_retention(retention, "Primera anulacion")
        self.assertTrue(retention.annulled_tfhka)
        with self.assertRaises(UserError):
            self.env['tfhka.retention.service'].annul_retention(retention, "Segunda anulacion")

    def test_32_generate_document_data_falsy_response(self):
        account_move = self._create_invoice()
        account_move.action_post()
        retention = self._create_retention("iva", account_move)
        retention.action_post()
        with patch(
            'odoo.addons.l10n_ve_invoice_digital.services.tfhka_client.TfhkaApiClient.emit',
            return_value=None,
        ):
            result = self.env['tfhka.retention.service'].generate_document_data(
                retention, "R00099", "05", True
            )
        self.assertIsNone(result)
        self.assertFalse(retention.is_digitalized)

    def test_33_generate_document_data_validation_sequence_false(self):
        account_move = self._create_invoice()
        account_move.action_post()
        retention = self._create_retention("iva", account_move)
        retention.action_post()
        with patch(
            'odoo.addons.l10n_ve_invoice_digital.services.tfhka_client.TfhkaApiClient._request'
        ) as mock_call:
            mock_call.return_value = {
                "resultado": {"numeroControl": "00-00000002"},
                "codigo": "200",
                "mensaje": "OK",
            }
            self.env['tfhka.retention.service'].generate_document_data(retention, "R00002", "05", False)
        self.assertTrue(retention.is_digitalized)
        messages = retention.message_ids.mapped('body')
        self.assertFalse(any("Warning accepted" in str(m) for m in messages))

    def test_34_prepare_identification_empty_recordset(self):
        result = self.env['tfhka.retention.service']._prepare_identification(
            self.env['account.retention'].browse([]), "05", "1"
        )
        self.assertIsNone(result)

    def test_35_prepare_identification_debit_origin(self):
        account_move = self._create_invoice()
        account_move.action_post()
        debit_note = self.env["account.move"].create({
            "move_type": "in_invoice",
            "partner_id": self.partner_a.id,
            "journal_id": self.journal.id,
            "invoice_date": fields.Date.today(),
            "debit_origin_id": account_move.id,
            "invoice_line_ids": [(0, 0, {
                "product_id": self.product.id,
                "quantity": 1,
                "price_unit": 100,
                "tax_ids": [(6, 0, [self.tax_iva16.id])],
            })],
        })
        debit_note.action_post()
        retention = self._create_retention("iva", debit_note)
        retention.action_post()
        ident = self.env['tfhka.retention.service']._prepare_identification(retention, "05", "1")
        self.assertEqual(ident["numeroFacturaAfectada"], str(account_move.sequence_number))

    def test_36_prepare_identification_reversed_entry(self):
        account_move = self._create_invoice()
        account_move.action_post()
        refund = self.env["account.move"].create({
            "move_type": "in_refund",
            "partner_id": self.partner_a.id,
            "journal_id": self.journal.id,
            "invoice_date": fields.Date.today(),
            "reversed_entry_id": account_move.id,
            "invoice_line_ids": [(0, 0, {
                "product_id": self.product.id,
                "quantity": 1,
                "price_unit": 100,
                "tax_ids": [(6, 0, [self.tax_iva16.id])],
            })],
        })
        refund.action_post()
        retention = self._create_retention("iva", refund)
        retention.action_post()
        ident = self.env['tfhka.retention.service']._prepare_identification(retention, "05", "1")
        self.assertEqual(ident["numeroFacturaAfectada"], str(account_move.sequence_number))

    def test_37_prepare_totals_empty_recordset(self):
        result = self.env['tfhka.retention.service']._prepare_totals(
            self.env['account.retention'].browse([]), "05"
        )
        self.assertIsNone(result)

    def test_38_prepare_detail_lines_base_currency_vef(self):
        account_move = self._create_invoice()
        account_move.action_post()
        retention = self._create_retention("iva", account_move)
        retention.action_post()
        retention.base_currency_is_vef = True
        details = self.env['tfhka.retention.service']._prepare_detail_lines(retention, "05")
        self.assertTrue(details)
        self.assertIn("montoTotal", details[0])

    # Boton unico de anulacion (action_cancel_retention): reemplaza a los dos
    # botones sueltos (nativo "Cancel" + "Cancel in TFHKA").
    def test_39_action_cancel_retention_not_digitized_cancels_directly(self):
        account_move = self._create_invoice()
        account_move.action_post()
        retention = self._create_retention("iva", account_move)
        retention.action_post()
        self.assertFalse(retention.is_digitalized)
        result = retention.action_cancel_retention()
        self.assertEqual(retention.state, "cancel")
        self.assertFalse(isinstance(result, dict) and result.get("res_model") == "tfhka.annul.wizard")

    def test_40_action_cancel_retention_digitized_opens_wizard(self):
        account_move = self._create_invoice()
        account_move.action_post()
        retention = self._create_retention("iva", account_move)
        retention.action_post()
        retention.is_digitalized = True
        action = retention.action_cancel_retention()
        self.assertEqual(action["res_model"], "tfhka.annul.wizard")
        self.assertEqual(action["context"]["default_retention_id"], retention.id)
        # No cancela todavia: falta confirmar el wizard con el motivo.
        self.assertEqual(retention.state, "emitted")

    @patch('odoo.addons.l10n_ve_invoice_digital.services.tfhka_client.TfhkaApiClient._request', side_effect=mock_api)
    def test_41_annul_wizard_confirm_chains_native_cancel(self, mock_call):
        account_move = self._create_invoice()
        account_move.action_post()
        retention = self._create_retention("iva", account_move)
        retention.action_post()
        retention.with_context(account_retention_alert=True).generate_document_digital()
        self.assertTrue(retention.is_digitalized)

        wizard = self.env['tfhka.annul.wizard'].create({
            'retention_id': retention.id,
            'reason': 'Error de emision',
        })
        wizard.action_confirm()
        # Un solo paso deja los dos lados consistentes: anulada en TFHKA y
        # cancelada en Odoo (pagos/conciliacion reversados).
        self.assertTrue(retention.annulled_tfhka)
        self.assertEqual(retention.state, "cancel")

    # Auto-digitalizacion condicionada al origen: si la retencion se postea
    # dentro de la cadena de account.move.action_post() (contexto propagado
    # por l10n_ve_invoice_digital/models/account_move.py), se auto-digitaliza;
    # si se postea manualmente (flujo individual, sin ese contexto), no.
    @patch('odoo.addons.l10n_ve_invoice_digital.services.tfhka_client.TfhkaApiClient._request', side_effect=mock_api)
    def test_42_action_post_with_invoice_context_auto_digitizes_iva(self, mock_call):
        account_move = self._create_invoice()
        account_move.action_post()
        retention = self._create_retention("iva", account_move)
        retention.with_context(l10n_ve_invoice_digital_auto_retention=True).action_post()
        self.assertTrue(retention.is_digitalized)

    @patch('odoo.addons.l10n_ve_invoice_digital.services.tfhka_client.TfhkaApiClient._request', side_effect=mock_api)
    def test_43_action_post_with_invoice_context_auto_digitizes_islr(self, mock_call):
        account_move = self._create_invoice()
        account_move.action_post()
        retention = self._create_retention("islr", account_move)
        retention.with_context(l10n_ve_invoice_digital_auto_retention=True).action_post()
        self.assertTrue(retention.is_digitalized)

    def test_44_action_post_without_invoice_context_stays_manual(self):
        account_move = self._create_invoice()
        account_move.action_post()
        retention = self._create_retention("iva", account_move)
        retention.action_post()
        # Flujo individual: sigue "emitted" sin digitalizar, con el boton
        # manual visible (show_digital_retention_iva=False => no invisible).
        self.assertFalse(retention.is_digitalized)
        self.assertFalse(retention.show_digital_retention_iva)

    @patch('odoo.addons.l10n_ve_invoice_digital.services.tfhka_client.TfhkaApiClient._request', side_effect=mock_api)
    def test_45_invoice_post_auto_digitizes_supplier_iva_retention(self, mock_call):
        # Extremo a extremo real: el contexto debe propagarse a traves de la
        # cadena de super() hasta l10n_ve_payment_extension, que crea y
        # postea la retencion IVA de proveedor al confirmar la factura.
        account_move = self._create_invoice()
        account_move.generate_iva_retention = True
        account_move.action_post()
        retention = self.env["account.retention"].search([
            ("type_retention", "=", "iva"),
            ("type", "=", "in_invoice"),
            ("partner_id", "=", self.partner_a.id),
        ], order="id desc", limit=1)
        self.assertTrue(retention, "La retencion IVA deberia haberse creado automaticamente al postear la factura")
        self.assertEqual(retention.state, "emitted")
        self.assertTrue(retention.is_digitalized)

    def test_46_prepare_detail_lines_monto_exento(self):
        tax_group_exento = self.env["account.tax.group"].create({"name": "Exento"})
        tax_exento = self.env["account.tax"].create({
            "name": "Exento",
            "amount": 0,
            "amount_type": "percent",
            "type_tax_use": "purchase",
            "tax_group_id": tax_group_exento.id,
        })
        invoice = self.env["account.move"].create({
            "move_type": "in_invoice",
            "partner_id": self.partner_a.id,
            "journal_id": self.journal.id,
            "invoice_date": fields.Date.today(),
            "invoice_line_ids": [
                (0, 0, {
                    "product_id": self.product.id,
                    "quantity": 2,
                    "price_unit": 100,
                    "tax_ids": [(6, 0, [self.tax_iva16.id])],
                    "price_subtotal": 200,
                    "price_total": 232,
                    "foreign_rate": 2.0,
                    "foreign_inverse_rate": 2.0,
                    "foreign_price": 200,
                    "foreign_subtotal": 400,
                    "foreign_price_total": 464,
                }),
                (0, 0, {
                    "product_id": self.product.id,
                    "quantity": 1,
                    "price_unit": 50,
                    "tax_ids": [(6, 0, [tax_exento.id])],
                    "price_subtotal": 50,
                    "price_total": 50,
                    "foreign_rate": 2.0,
                    "foreign_inverse_rate": 2.0,
                    "foreign_price": 50,
                    "foreign_subtotal": 100,
                    "foreign_price_total": 100,
                }),
            ],
        })
        invoice.action_post()
        retention = self._create_retention("iva", invoice)
        retention.action_post()
        # base_currency_is_vef=True fuerza la lectura de groups_by_subtotal
        # (montos base), el mismo grupo que ya usan otros tests de este
        # archivo (ver test_38) para evitar depender de como se propagan los
        # campos foreign_* de linea hacia tax_totals en facturas de compra.
        retention.base_currency_is_vef = True

        details = self.env['tfhka.retention.service']._prepare_detail_lines(retention, "05")
        self.assertTrue(details)
        self.assertEqual(details[0]["montoExento"], "50.0")

    # # Retencion con Sucursal
    # @patch('odoo.addons.l10n_ve_invoice_digital.services.tfhka_client.TfhkaApiClient._request', side_effect=mock_api)
    # def test_12_generate_document_digital_subsidiary_succes(self, mock_call):
    #     self.company.write({"subsidiary": True})
    #     subsidiary = self._create_subsidiary()

    #     account_move = self._create_invoice()
    #     retention = self._create_retention("iva", account_move, "20230800000003", subsidiary)

    #     retention.generate_document_digital()
    #     self.assertEqual(retention.is_digitalized, True)
    #     _logger.info("Test passed: Digital document with subsidiary successfully generated.")

    # # Error de referencia de Retencion con Sucursal
    # @patch('odoo.addons.l10n_ve_invoice_digital.services.tfhka_client.TfhkaApiClient._request', side_effect=mock_api)
    # def test_13_generate_document_digital_subsidiary_error(self, mock_call):
    #     self.company.write({"subsidiary": True})
    #     subsidiary = self._create_subsidiary()
    #     subsidiary.code = ""
    #     account_move = self._create_invoice()
    #     retention = self._create_retention("iva", account_move, "20230800000003", subsidiary)

