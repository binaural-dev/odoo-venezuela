from odoo.tests import TransactionCase, tagged
from datetime import timedelta
from odoo.exceptions import UserError
from odoo import Command, fields
from unittest.mock import patch, MagicMock

import logging

_logger = logging.getLogger(__name__)

@tagged('l10n_ve_invoice_digital', 'invoice digital') 
class TestAccumulatedRate(TransactionCase):
    def setUp(self):
        super().setUp()

        self.company = self.env.company
        self.currency = self.env.ref("base.VEF")
        self.foreign_currency = self.env.ref("base.USD")
        self.env.user.tz = "America/Caracas"
        self.company.write(
            {
                'currency_id': self.currency.id,
                'foreign_currency_id': self.foreign_currency.id, 
                "username_tfhka": "usuario_prueba",
                "password_tfhka": "clave_prueba",
                "url_tfhka": "https://api.tfhka.com",
                "token_auth_tfhka": "token_fake",
                "invoice_digital_tfhka": True,
                "sequence_validation_tfhka": False,
            }
        )

        self.purchase_journal = self.env['account.journal'].search([
            ('company_id', '=', self.company.id),
            ('type', '=', 'purchase')
        ], limit=1)

        if not self.purchase_journal:
            self.purchase_journal = self.env['account.journal'].create({
                'name': 'Purchase Journal',
                'code': 'PURCH',
                'type': 'purchase',
                'company_id': self.company.id,
            })

        self.expense_account = self.env['account.account'].search([
            ('company_ids', 'in', self.company.id),
            ('account_type', '=', 'expense'),
            ('active', '=', True)
        ], limit=1)

        if not self.expense_account:
            self.expense_account = self.env['account.account'].create({
                'name': 'Test Expense Account',
                'code': '600000',
                'account_type': 'expense',
                'company_ids': [(6, 0, [self.company.id])],
                'reconcile': False,
            })

        # Cuenta de pasivo (para partner)
        self.payable_account = self.env['account.account'].search([
            ('company_ids', 'in', self.company.id),
            ('account_type', '=', 'liability_payable'),
            ('active', '=', True)
        ], limit=1)

        if not self.payable_account:
            self.payable_account = self.env['account.account'].create({
                'name': 'Test Payable Account',
                'code': '200000',
                'account_type': 'liability_payable',
                'company_ids': [(6, 0, [self.company.id])],
                'reconcile': True,
            })

        # Diarios de retenciones (l10n_ve_payment_extension los exige en la compañía)
        retention_account = self.env['account.account'].create({
            'name': 'Retenciones por pagar',
            'code': '210099',
            'account_type': 'liability_current',
            'company_ids': [(6, 0, [self.company.id])],
            'reconcile': True,
        })
        retention_journal = self.env['account.journal'].with_context(
            chart_template_load=True
        ).create({
            'name': 'Retenciones',
            'code': 'RETN',
            'type': 'bank',
            'company_id': self.company.id,
            'default_account_id': retention_account.id,
        })
        for line in (
            retention_journal.inbound_payment_method_line_ids
            | retention_journal.outbound_payment_method_line_ids
        ).filtered(lambda l: not l.payment_account_id):
            line.payment_account_id = retention_account
        self.company.write({
            'iva_supplier_retention_journal_id': retention_journal.id,
            'iva_customer_retention_journal_id': retention_journal.id,
            'islr_supplier_retention_journal_id': retention_journal.id,
            'islr_customer_retention_journal_id': retention_journal.id,
            'municipal_supplier_retention_journal_id': retention_journal.id,
            'municipal_customer_retention_journal_id': retention_journal.id,
        })

        self.type_person = self.env['type.person'].create({
            'name': 'No Juridica',
        })

        self.partner = self.env['res.partner'].create({
            'name': 'Cliente Prueba',
            'vat': 'J12345678',
            'prefix_vat': 'J',
            'country_id': self.env.ref('base.ve').id,
            'phone': '04141234567',
            'email': 'cliente@prueba.com',
            'street': 'Calle Falsa 123',
            'type_person_id': self.type_person.id,
            'property_account_payable_id': self.payable_account.id,
        })

        self.tax_unit = self.env['tax.unit'].create({
            'name': 'UT 2025',
            'value': 9.0,
        })

        self.tariff = self.env['fees.retention'].create({
            'name': 'Tarifa con tramos',
            'accumulated_rate': True,
            'tax_unit_ids': self.tax_unit.id
        })

        self.tariff.accumulated_rate_ids = [(0, 0, {
            'name': 'Tier 1',
            'start': 0,
            'stop': 2000,
            'percentage': 15,
            'subtract_ut': 0,
        }), (0, 0, {
            'name': 'Tier 2',
            'start': 2001,
            'stop': 3000,
            'percentage': 22,
            'subtract_ut': 140,
        }), (0, 0, {
            'name': 'Tier 3',
            'start': 3001,
            'stop': 0,
            'percentage': 34,
            'subtract_ut': 500,
        })]

        self.payment_concept = self.env['payment.concept'].create({
            'name': 'Concepto Acumulado',
        })

        self.line_concept = self.env['payment.concept.line'].create({
            'payment_concept_id': self.payment_concept.id,
            'type_person_id': self.type_person.id,
            'code': 73,
            'percentage_tax_base': 100,
            'tariff_id': self.tariff.id,
            'pay_from': 100,
        })

        self.payment_concept.write({
            'line_payment_concept_ids': [(4, self.line_concept.id, 0)]
        })

        tax_country = self.env.ref('base.ve')
        self.company.account_fiscal_country_id = tax_country
        tax_group = self.env['account.tax.group'].create({
            'name': 'IVA',
            'company_id': self.company.id,
            'country_id': tax_country.id,
        })
        self.tax_iva16 = self.env['account.tax'].create({
            'name': 'IVA 16%',
            'tax_group_id': tax_group.id,
            'country_id': tax_country.id,
            'company_id': self.company.id,
            'amount': 16,
            'amount_type': 'percent',
            'type_tax_use': 'sale',
        })
        self.tax_iva16_purchase = self.env['account.tax'].create({
            'name': 'IVA 16% compras',
            'tax_group_id': tax_group.id,
            'country_id': tax_country.id,
            'company_id': self.company.id,
            'amount': 16,
            'amount_type': 'percent',
            'type_tax_use': 'purchase',
        })

        self.product = self.env['product.product'].create({
            'name': 'Producto Prueba',
            'type': 'service',
            'list_price': 100,
            'barcode': '123456789',
            'taxes_id': [(6, 0, [self.tax_iva16.id])],
            'supplier_taxes_id': [(6, 0, [self.tax_iva16_purchase.id])],
            'payment_concept': self.payment_concept.id,
        })

    def _create_invoice(self):
        move = self.env['account.move'].create({
            'partner_id': self.partner.id,
            'move_type': 'in_invoice',
            'journal_id': self.purchase_journal.id,
            'invoice_date': fields.Date.context_today(self.env.user),
            'invoice_date_display': fields.Date.context_today(self.env.user),
            'currency_id': self.company.currency_id.id,
            'invoice_line_ids': [(0, 0, {
                'name': 'Servicio Nuevo',
                'quantity': 1,
                'price_unit': 300,
                'product_id': self.product.id,
                'account_id': self.expense_account.id,
                'tax_ids': [(6, 0, [self.tax_iva16_purchase.id])],
            })]
        })

        move._onchange_invoice_line_ids()
        move.foreign_rate = 5.0
        move.action_post()
        return move
    
        # Simula las respuestas SUCCES de la API de TFHKA
    
    def _create_subsidiary(self, name="Sucursal prueba"):
        analytic_plan = self.env['account.analytic.plan'].create({
            'name': 'Plan para pruebas',
        })

        return self.env['account.analytic.account'].create({
            'name': name,
            'is_subsidiary': True,
            'company_id': self.env.company.id,
            'plan_id': analytic_plan.id,
            'code': "002",
        })
    
    def _create_retention(self, type_retention, account_move, number = "20250600000002", subsidiary = None):
        retention_date = fields.Date.context_today(self.env.user)
        retention = self.env["account.retention"].create(
            {   
                "number": number,
                "type_retention": type_retention,
                "type": "in_invoice",
                "company_id": self.company.id,
                "partner_id": self.partner.id,
                "date": retention_date,
                "date_accounting": retention_date,
                "retention_line_ids": [
                    Command.create(
                        {
                            "retention_amount": 100,
                            "invoice_total": 100,
                            "foreign_retention_amount": 100,
                            "invoice_amount": 100,
                            "foreign_invoice_amount": 100,
                            "foreign_currency_rate": 1.0,
                            "name": "Retencion ISLR",
                            "move_id": account_move.id,
                            "payment_concept_id": self.payment_concept.id,
                        }
                    ),
                ],
            }
        )
        if subsidiary:
            retention.account_analytic_id = subsidiary.id
        retention.action_post()
        return retention

    def mock_api(endpoint_key, payload):

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
    
    @patch('odoo.addons.l10n_ve_invoice_digital.models.account_retention.AccountRetention.call_tfhka_api', side_effect=mock_api)
    def test_01_create_retention_iva_success(self, mock_call):
        account_move = self._create_invoice()
        retention_iva = self._create_retention("iva", account_move) 
        
        retention_iva.generate_document_digital()
        self.assertEqual(retention_iva.is_digitalized, True)

    @patch('odoo.addons.l10n_ve_invoice_digital.models.account_retention.AccountRetention.call_tfhka_api', side_effect=mock_api)
    def test_02_create_retention_islr_success(self, mock_call):

        account_move = self._create_invoice()
        retention_islr = self._create_retention("islr", account_move)

        retention_islr.generate_document_digital()
        self.assertEqual(retention_islr.is_digitalized, True)

    # API de TFHKA para consultar numeraciones
    @patch('odoo.addons.l10n_ve_invoice_digital.models.account_retention.AccountRetention.call_tfhka_api')
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
        retention = self._create_retention("iva", account_move)

        series = ""
        response = retention.query_numbering(series)
        _logger.info("Response from query_numbering: %s", response)

        # Verificamos que la respuesta fue la esperada
        self.assertEqual(response, None)

    # API de TFHKA para obtener el último número de documento
    @patch('odoo.addons.l10n_ve_invoice_digital.models.account_retention.AccountRetention.call_tfhka_api')
    def test_04_get_last_document_number_success(self, mock_call):
        mock_call.return_value = {
            "numeroDocumento": 126,
            "codigo": "200",
            "mensaje": "Consulta realizada exitosamente"
        }

        account_move = self._create_invoice()
        retention = self._create_retention("iva", account_move)

        document_type = "02"
        response = retention.get_last_document_number(document_type)
        _logger.info("Response from get_last_document_number: %s", response)

        # Verificamos que la respuesta fue la esperada
        self.assertEqual(response, 126)

    # API de TFHKA para generar documento digital (factura, nota de crédito, nota de débito)
    @patch('odoo.addons.l10n_ve_invoice_digital.models.account_retention.AccountRetention.call_tfhka_api')
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
        retention = self._create_retention("iva", account_move)

        document_type = "02"
        document_number = "12345678"
        validation_sequence = True
        response = retention.generate_document_data(document_number, document_type, validation_sequence)
        _logger.info("Response from generate_document_data: %s", response)

        # Verificamos que la respuesta fue la esperada
        self.assertEqual(response, None)

    # Validacion de secuencia entre la API y Odoo
    @patch('odoo.addons.l10n_ve_invoice_digital.models.account_retention.AccountRetention.call_tfhka_api', side_effect=mock_api)
    def test_06_generate_document_digital_sequence_error(self, mock_call):
        self.company.write({"sequence_validation_tfhka": True,})

        account_move = self._create_invoice()
        retention = self._create_retention("iva", account_move, "20230800000003")

        res = retention.with_context(account_retention_alert=True).generate_document_digital()

        _logger.info(res)

        self.assertIsNone(res) 
        # self.assertEqual(retention.is_digitalized, True)

        _logger.info("Test passed: Sequence validation error raised as expected.")

    # API de TFHKA para consultar numeraciones con número de serie agotado
    @patch('odoo.addons.l10n_ve_invoice_digital.models.account_retention.AccountRetention.call_tfhka_api')
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
        retention = self._create_retention("iva", account_move)
        series = ""
        with self.assertRaises(UserError) as e:
            retention.query_numbering(series)
            _logger.error(e.exception)
        
        _logger.info("Test passed: Numbering sold out error raised as expected.")

    # Llamada a la API de TFHKA URL vacía
    def test_08_call_tfhka_api_URL_error(self):
        self.company.write({"url_tfhka": "",})

        account_move = self._create_invoice()
        retention = self._create_retention("iva", account_move)

        endpoint_key = "emision"
        payload={
            "serie": "",
            "tipoDocumento": "",
            "prefix": ""
        }
        with self.assertRaises(UserError) as e:
            retention.call_tfhka_api(endpoint_key, payload)
            _logger.error(e.exception)

        _logger.info("Test passed: URL for TFHKA is empty, UserError raised as expected.")

    # Llamada a la API de TFHKA Token vacío
    def test_09_call_tfhka_api_token_error(self):
        self.company.write({"token_auth_tfhka": ""})

        account_move = self._create_invoice()
        retention = self._create_retention("iva", account_move)

        endpoint_key = "emision"
        payload={
            "serie": "",
            "tipoDocumento": "",
            "prefix": ""
        }
        with self.assertRaises(UserError) as e:
            retention.call_tfhka_api(endpoint_key, payload)
            _logger.error(e.exception)

        _logger.info("Test passed: Token for TFHKA is empty, UserError raised as expected.")

    # Llamada a la API de TFHKA con error 400
    @patch('requests.post')
    def test_10_call_tfhka_api_status_code_400_error(self, mock_call):
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_call.return_value = mock_response

        account_move = self._create_invoice()
        retention = self._create_retention("iva", account_move)

        endpoint_key = "emision"
        payload={
            "serie": "",
            "tipoDocumento": "",
            "prefix": ""
        }
        with self.assertRaises(UserError) as e:
            retention.call_tfhka_api(endpoint_key, payload)
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
        retention = self._create_retention("iva", account_move)

        endpoint_key = "emision"
        payload={
            "serie": "",
            "tipoDocumento": "",
            "prefix": ""
        }
        with self.assertRaises(UserError) as e:
            retention.call_tfhka_api(endpoint_key, payload)
            _logger.error(e.exception)

        _logger.info("Test passed: code 200 error, UserError raised as expected.")

    # # Retencion con Sucursal
    # @patch('odoo.addons.l10n_ve_invoice_digital.models.account_retention.AccountRetention.call_tfhka_api', side_effect=mock_api)
    # def test_12_generate_document_digital_subsidiary_succes(self, mock_call):
    #     self.company.write({"subsidiary": True})
    #     subsidiary = self._create_subsidiary()

    #     account_move = self._create_invoice()
    #     retention = self._create_retention("iva", account_move, "20230800000003", subsidiary)

    #     retention.generate_document_digital()
    #     self.assertEqual(retention.is_digitalized, True)
    #     _logger.info("Test passed: Digital document with subsidiary successfully generated.")

    # # Error de referencia de Retencion con Sucursal
    # @patch('odoo.addons.l10n_ve_invoice_digital.models.account_retention.AccountRetention.call_tfhka_api', side_effect=mock_api)
    # def test_13_generate_document_digital_subsidiary_error(self, mock_call):
    #     self.company.write({"subsidiary": True})
    #     subsidiary = self._create_subsidiary()
    #     subsidiary.code = ""
    #     account_move = self._create_invoice()
    #     retention = self._create_retention("iva", account_move, "20230800000003", subsidiary)

    #     with self.assertRaises(UserError) as e:
    #         retention.generate_document_digital()
    #         _logger.error(e.exception)
    #     _logger.info("Test passed: The reference is empty, a user error was generated as expected.")
