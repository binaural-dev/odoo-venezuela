from odoo.exceptions import UserError
from odoo import fields, Command
from odoo.tests import TransactionCase, tagged
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)

@tagged('l10n_ve_invoice_digital', 'invoice digital') 
class TestAccountMoveApiCalls(TransactionCase):

    def setUp(self):
        super().setUp()
        Account = self.env["account.account"]
        Journal = self.env["account.journal"]
        self.env.user.tz = "America/Caracas"

        # ───────────────────────────────────────────────────── monedas
        self.company = self.env.ref("base.main_company")
        self.currency_usd = self.env.ref("base.USD")
        self.currency_vef = self.env.ref("base.VEF")

        self.company.write(
            {
                "currency_id": self.currency_usd.id,
                "currency_foreign_id": self.currency_vef.id,
                "invoice_digital_tfhka": True,
            }
        )

        # ───────────────────────────────────────────────────── helpers
        def acc(code, ttype, name, recon=False):
            a = Account.search(
                [("code", "=", code), ("company_id", "=", self.company.id)], limit=1
            )
            if not a:
                a = Account.create(
                    {
                        "name": name,
                        "code": code,
                        "account_type": ttype,
                        "reconcile": recon,
                        "company_id": self.company.id,
                    }
                )
            return a

        # ───────────────────────────────────────────────────── cuentas
        self.acc_receivable = acc("1101", "asset_receivable", "CxC", True)
        self.acc_income = acc("4001", "income", "Ingresos")
        self.acc_igtf_cli = acc("236IGTF", "expense", "IGTF Clientes")

        # anticipo pasivo ↔️ activo
        self.advance_cust_acc = acc(
            "21600", "liability_current", "Anticipo Clientes", True
        )
        self.advance_supp_acc = acc(
            "13600", "asset_current", "Anticipo Proveedores", True
        )

        # ───────────────────────────────────────────────────── diarios

        # Crear el diario y secuencia
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
        note_sequence = self.env['ir.sequence'].create({
            'name': 'nota de debito',
            'code': '',
            'prefix': 'ND/',
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

        self.debit_journal = self.env['account.journal'].create({
            'name': 'Nota de Debito',
            'code': '',
            'type': 'sale',
            'sequence_id': note_sequence.id,
            "refund_sequence_id": refund_sequence.id,
            'company_id': self.env.company.id,
        })

        self.bank_journal_usd = (
            Journal.search(
                [("type", "=", "bank"), ("currency_id", "=", self.currency_usd.id)],
                limit=1,
            )
            or Journal.create(
                {
                    "name": "Banco USD",
                    "code": "BNKUS",
                    "type": "bank",
                    "currency_id": self.currency_usd.id,
                    "company_id": self.company.id,
                }
            )
        )
        self.bank_journal_usd.write({"is_igtf": True})

        # ➡️ Diario puente para “cruce anticipo + IGTF”
        self.cross_journal = Journal.create(
            {
                "name": "Cruce Anticipo IGTF",
                "code": "CRIG",
                "type": "general",
                "company_id": self.company.id,
            }
        )

        # ───────────────────────────────────────────────────── compañía
        self.company.write(
            {
                "igtf_percentage": 3.0,
                "customer_account_igtf_id": self.acc_igtf_cli.id,
            }
        )

        # ───────────────────────────────────────── método de pago manual
        manual_in = self.env.ref("account.account_payment_method_manual_in")
        self.pm_line_in_usd = (
            self.env["account.payment.method.line"].search(
                [
                    ("journal_id", "=", self.bank_journal_usd.id),
                    ("payment_method_id", "=", manual_in.id),
                    ("payment_type", "=", "inbound"),
                ],
                limit=1,
            )
            or self.env["account.payment.method.line"].create(
                {
                    "name": "Manual Inbound USD",
                    "journal_id": self.bank_journal_usd.id,
                    "payment_method_id": manual_in.id,
                    "payment_type": "inbound",
                }
            )
        )

        # ───────────────────────────────────────────────── partner/product
        self.partner = self.env['res.partner'].create({
            'name': 'Cliente Prueba',
            'vat': 'J12345678',
            'prefix_vat': 'J',
            'country_id': self.env.ref('base.ve').id,
            'phone': '04141234567',
            'email': 'cliente@prueba.com',
            'street': 'Calle Falsa 123',
        })

        # Crear impuesto IVA 16%
        self.tax_iva16 = self.env['account.tax'].create({
            'name': 'IVA 16%',
            'amount': 16,
            'amount_type': 'percent',
            'type_tax_use': 'sale',
        })

        # Crear el producto
        self.product = self.env['product.product'].create({
            'name': 'Producto Prueba',
            'type': 'service',
            'list_price': 100,
            'barcode': '123456789',
            'taxes_id': [(6, 0, [self.tax_iva16.id])],
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
            "partner_id": self.partner.id,
            "foreign_currency_id": self.currency_vef.id,
            "currency_id": self.currency_usd.id,
            "state": "draft",
            "foreign_rate": foreign_rate,
            "foreign_inverse_rate": foreign_inverse_rate,
            "manually_set_rate": True,
            "invoice_line_ids": invoice_lines,
            "invoice_date": fields.Date.today(),
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

    def _create_payment(
        self,
        amount=100,
        *,
        currency=None,
        journal=None,
        fx_rate=None,
        fx_rate_inv=None,
        pm_line=None,
    ):
        """Crea y valida un payment genérico."""
        currency = currency or self.currency_usd
        journal = journal or self.bank_journal_usd
        pm_line = pm_line or self.pm_line_in_usd

        vals = {
            "payment_type": "inbound",
            "partner_type": "customer",
            "partner_id": self.partner.id,
            "amount": amount,
            "currency_id": currency.id,
            "journal_id": journal.id,
            "payment_method_line_id": pm_line.id,
            "date": fields.Date.today(),
        }
        if fx_rate:
            vals.update({"foreign_rate": fx_rate, "foreign_inverse_rate": fx_rate_inv})

        pay = self.env["account.payment"].create(vals)
        pay.action_post()
        _logger.debug(f"Pago creado → {pay.name} | monto {amount} {currency.name}")
        return pay
    
    # Simula las respuestas SUCCES de la API de TFHKA
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
        
    # API de TFHKA para consultar numeraciones
    @patch('odoo.addons.l10n_ve_invoice_digital.models.account_move.AccountMove.call_tfhka_api')
    def test_01_query_numbering_success(self, mock_call):

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

        self.invoice = self._create_invoice(
            products=[
                {
                    "product_id": self.product.id,
                    "price_unit": 1,
                    "tax_ids": [self.tax_iva16.id],
                }
            ]
        )

        series = ""
        response = self.invoice.query_numbering(series)
        _logger.info("Response from query_numbering: %s", response)

        # Verificamos que la respuesta fue la esperada
        self.assertEqual(response, None)

    # API de TFHKA para obtener el último número de documento
    @patch('odoo.addons.l10n_ve_invoice_digital.models.account_move.AccountMove.call_tfhka_api')
    def test_02_get_last_document_number_success(self, mock_call):
        mock_call.return_value = {
            "numeroDocumento": 126,
            "codigo": "200",
            "mensaje": "Consulta realizada exitosamente"
        }

        self.invoice = self._create_invoice(
            products=[
                {
                    "product_id": self.product.id,
                    "price_unit": 1,
                    "tax_ids": [self.tax_iva16.id],
                }
            ]
        )

        series = ""
        document_type = "02"
        response = self.invoice.get_last_document_number(document_type, series)
        _logger.info("Response from get_last_document_number: %s", response)

        # Verificamos que la respuesta fue la esperada
        # self.assertEqual(response, None)

    # API de TFHKA para generar documento digital (factura, nota de crédito, nota de débito)
    @patch('odoo.addons.l10n_ve_invoice_digital.models.account_move.AccountMove.call_tfhka_api')
    def test_03_generate_document_data_success(self, mock_call):
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

        self.invoice = self._create_invoice(
            products=[
                {
                    "product_id": self.product.id,
                    "price_unit": 1,
                    "tax_ids": [self.tax_iva16.id],
                }
            ]
        )

        series = ""
        document_type = "02"
        document_number = "12345678"
        response = self.invoice.generate_document_data(document_number, document_type, series)
        _logger.info("Response from generate_document_data: %s", response)

        # Verificamos que la respuesta fue la esperada
        # self.assertEqual(response, None)

    # Factura de cliente
    @patch('odoo.addons.l10n_ve_invoice_digital.models.account_move.AccountMove.call_tfhka_api', side_effect=mock_api)
    def test_04_generate_document_digital_success(self, mock_call):

        self.invoice = self._create_invoice(
            products=[
                {
                    "product_id": self.product.id,
                    "price_unit": 1,
                    "tax_ids": [self.tax_iva16.id],
                }
            ]
        )
        
        self.invoice.generate_document_digital()
        self.assertEqual(self.invoice.is_digitalized, True)
        _logger.info("Test passed: Document digital generated successfully.")

    # Nota de crédito
    @patch('odoo.addons.l10n_ve_invoice_digital.models.account_move.AccountMove.call_tfhka_api', side_effect=mock_api)
    def test_05_generate_document_digital_credit_note_success(self, mock_call):

        self.invoice = self._create_invoice(
            products=[
                {
                    "product_id": self.product.id,
                    "price_unit": 1,
                    "tax_ids": [self.tax_iva16.id],
                }
            ]
        )

        self.credit_note = self._create_invoice(
            products=[
                {
                    "product_id": self.product.id,
                    "price_unit": 1,
                    "tax_ids": [self.tax_iva16.id],
                }
            ],
            move_type="out_refund",
            reversed_entry_id=self.invoice,
        )

        response = self.invoice.generate_document_digital()
        _logger.info("Response from generate_document_digital: %s", response)

        self.assertEqual(self.invoice.is_digitalized, True)

    # Nota de debito
    @patch('odoo.addons.l10n_ve_invoice_digital.models.account_move.AccountMove.call_tfhka_api', side_effect=mock_api)
    def test_06_generate_document_digital_debit_note_success(self, mock_call):

        self.invoice = self._create_invoice(
            products=[
                {
                    "product_id": self.product.id,
                    "price_unit": 1,
                    "tax_ids": [self.tax_iva16.id],
                }
            ]
        )

        self.debit_note = self._create_invoice(
            products=[
                {
                    "product_id": self.product.id,
                    "price_unit": 1,
                    "tax_ids": [self.tax_iva16.id],
                }
            ],
            debit_origin_id=self.invoice,
        )
        self.debit_note.action_post()

        response = self.invoice.generate_document_digital()
        _logger.info("Response from generate_document_digital: %s", response)

        self.assertEqual(self.invoice.is_digitalized, True)

    # Validacion de secuencia entre la API y Odoo
    @patch('odoo.addons.l10n_ve_invoice_digital.models.account_move.AccountMove.call_tfhka_api', side_effect=mock_api)
    def test_07_generate_document_digital_sequence_error(self, mock_call):

        self.journal.sequence_id.number_next_actual = 3
        self.invoice = self._create_invoice(
            products=[
                {
                    "product_id": self.product.id,
                    "price_unit": 1,
                    "tax_ids": [self.tax_iva16.id],
                }
            ]
        )

        with self.assertRaises(UserError) as e:
            self.invoice.generate_document_digital()
            _logger.error(e.exception)

        _logger.info("Test passed: Sequence validation error raised as expected.")

    # Factura de cliente con serie
    @patch('odoo.addons.l10n_ve_invoice_digital.models.account_move.AccountMove.call_tfhka_api', side_effect=mock_api)
    def test_08_generate_document_digital_series_success(self, mock_call):

        control_number_series = self.env['ir.sequence'].create({
            'name': 'Número de Control para Series A',
            'prefix': '',
            'code': 'series.invoice.correlative',
            'padding': 5,
            "number_next_actual": 1,
        })
        serie_secuencial = self.env['ir.sequence'].create({
            'name': 'Secuencia Facturas de cliente serie A',
            'prefix': 'A-',
            'padding': 8,
            "number_next_actual": 2,
        })
        self.company.group_sales_invoicing_series = True
        self.journal.write({
            'series_correlative_sequence_id': control_number_series.id,
            'sequence_id': serie_secuencial.id,
        })

        self.invoice = self._create_invoice(
            products=[
                {
                    "product_id": self.product.id,
                    "price_unit": 1,
                    "tax_ids": [self.tax_iva16.id],
                }
            ]
        )

        self.invoice.generate_document_digital()
        self.assertEqual(self.invoice.is_digitalized, True)
        _logger.info("Test passed: Document digital generated successfully.")

    # Validacion de Series
    @patch('odoo.addons.l10n_ve_invoice_digital.models.account_move.AccountMove.call_tfhka_api', side_effect=mock_api)
    def test_09_generate_document_digital_series_prefix_error(self, mock_call):

        control_number_series = self.env['ir.sequence'].create({
            'name': 'Número de Control para Series A',
            'prefix': '',
            'code': 'series.invoice.correlative',
            'padding': 5,
            "number_next_actual": 1,
        })
        serie_secuencial = self.env['ir.sequence'].create({
            'name': 'Secuencia Facturas de cliente serie A',
            'prefix': '',
            'padding': 8,
            "number_next_actual": 2,
        })
        self.company.group_sales_invoicing_series = True
        self.journal.write({
            'series_correlative_sequence_id': control_number_series.id,
            'sequence_id': serie_secuencial.id,
        })

        self.invoice = self._create_invoice(
            products=[
                {
                    "product_id": self.product.id,
                    "price_unit": 1,
                    "tax_ids": [self.tax_iva16.id],
                }
            ]
        )

        with self.assertRaises(UserError) as e:
            self.invoice.generate_document_digital()
            _logger.error(e.exception)

        _logger.info("Test passed: Series prefix validation error raised as expected.")

    # API de TFHKA para consultar numeraciones con número de serie agotado
    @patch('odoo.addons.l10n_ve_invoice_digital.models.account_move.AccountMove.call_tfhka_api')
    def test_10_query_numbering_numbering_sold_out_error(self, mock_call):

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

        self.invoice = self._create_invoice(
            products=[
                {
                    "product_id": self.product.id,
                    "price_unit": 1,
                    "tax_ids": [self.tax_iva16.id],
                }
            ]
        )

        series = ""

        with self.assertRaises(UserError) as e:
            self.invoice.query_numbering(series)
            _logger.error(e.exception)
        
        _logger.info("Test passed: Numbering sold out error raised as expected.")

    # Llamada a la API de TFHKA URL vacía
    def test_11_call_tfhka_api_URL_error(self):
        self.company.write(
            {
                "username_tfhka": "usuario_prueba",
                "password_tfhka": "clave_prueba",
                "url_tfhka": "",
                "token_auth_tfhka": "token_fake",
                "invoice_digital_tfhka": True,
                "sequence_validation_tfhka": True,
            }
        )

        self.invoice = self._create_invoice(
            products=[
                {
                    "product_id": self.product.id,
                    "price_unit": 1,
                    "tax_ids": [self.tax_iva16.id],
                }
            ]
        )

        endpoint_key = "emision"
        payload={
            "serie": "",
            "tipoDocumento": "",
            "prefix": ""
        }
        with self.assertRaises(UserError) as e:
            self.invoice.call_tfhka_api(endpoint_key, payload)
            _logger.error(e.exception)

        _logger.info("Test passed: URL for TFHKA is empty, UserError raised as expected.")

    # Llamada a la API de TFHKA Token vacío
    def test_12_call_tfhka_api_token_error(self):
        self.company.write(
            {
                "username_tfhka": "usuario_prueba",
                "password_tfhka": "clave_prueba",
                "url_tfhka": "https://api.tfhka.com",
                "token_auth_tfhka": "",
                "invoice_digital_tfhka": True,
                "sequence_validation_tfhka": True,
            }
        )

        self.invoice = self._create_invoice(
            products=[
                {
                    "product_id": self.product.id,
                    "price_unit": 1,
                    "tax_ids": [self.tax_iva16.id],
                }
            ]
        )

        endpoint_key = "emision"
        payload={
            "serie": "",
            "tipoDocumento": "",
            "prefix": ""
        }
        with self.assertRaises(UserError) as e:
            self.invoice.call_tfhka_api(endpoint_key, payload)
            _logger.error(e.exception)

        _logger.info("Test passed: Token for TFHKA is empty, UserError raised as expected.")

    # Llamada a la API de TFHKA con error 400
    @patch('requests.post')
    def test_13_call_tfhka_api_status_code_400_error(self, mock_call):
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_call.return_value = mock_response

        self.company.write(
            {
                "username_tfhka": "usuario_prueba",
                "password_tfhka": "clave_prueba",
                "url_tfhka": "https://api.tfhka.com",
                "token_auth_tfhka": "token_fake",
                "invoice_digital_tfhka": True,
                "sequence_validation_tfhka": True,
            }
        )

        self.invoice = self._create_invoice(
            products=[
                {
                    "product_id": self.product.id,
                    "price_unit": 1,
                    "tax_ids": [self.tax_iva16.id],
                }
            ]
        )

        endpoint_key = "emision"
        payload={
            "serie": "",
            "tipoDocumento": "",
            "prefix": ""
        }
        with self.assertRaises(UserError) as e:
            self.invoice.call_tfhka_api(endpoint_key, payload)
            _logger.error(e.exception)

        _logger.info("Test passed: code 400 error, UserError raised as expected.")

    # Llamada a la API de TFHKA con error 200 pero con mensaje de error
    @patch('requests.post')
    def test_14_call_tfhka_api_status_code_200_error(self, mock_call):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "codigo": "400",
            "mensaje": "Error en la petición"
        }
        mock_call.return_value = mock_response

        self.company.write(
            {
                "username_tfhka": "usuario_prueba",
                "password_tfhka": "clave_prueba",
                "url_tfhka": "https://api.tfhka.com",
                "token_auth_tfhka": "token_fake",
                "invoice_digital_tfhka": True,
                "sequence_validation_tfhka": True,
            }
        )

        self.invoice = self._create_invoice(
            products=[
                {
                    "product_id": self.product.id,
                    "price_unit": 1,
                    "tax_ids": [self.tax_iva16.id],
                }
            ]
        )

        endpoint_key = "emision"
        payload={
            "serie": "",
            "tipoDocumento": "",
            "prefix": ""
        }
        with self.assertRaises(UserError) as e:
            self.invoice.call_tfhka_api(endpoint_key, payload)
            _logger.error(e.exception)

        _logger.info("Test passed: code 200 error, UserError raised as expected.")

    # Validacion de factura sin digitalizar
    @patch('odoo.addons.l10n_ve_invoice_digital.models.account_move.AccountMove.call_tfhka_api', side_effect=mock_api)
    def test_15_generate_document_digital_has_not_been_digitized_error(self, mock_call):

        self.invoice = self._create_invoice(
            products=[
                {
                    "product_id": self.product.id,
                    "price_unit": 1,
                    "tax_ids": [self.tax_iva16.id],
                }
            ]
        )

        self.env['move.action.post.alert.wizard'].create({
            'move_id': self.invoice.id
        }).action_confirm()

        invoice = self._create_invoice(
            products=[
                {
                    "product_id": self.product.id,
                    "price_unit": 1,
                    "tax_ids": [self.tax_iva16.id],
                }
            ]
        )
        
        with self.assertRaises(UserError) as e:        
            self.env['move.action.post.alert.wizard'].create({
                'move_id': invoice.id
            }).action_confirm()

            _logger.info(e.exception)
        _logger.info("Test passed: ")

    # Validacion de fecha
    @patch('odoo.addons.l10n_ve_invoice_digital.models.account_move.AccountMove.call_tfhka_api', side_effect=mock_api)
    def test_16_generate_document_digital_validation_expiration_date_error(self, mock_call):

        self.invoice = self._create_invoice(
            products=[
                {
                    "product_id": self.product.id,
                    "price_unit": 1,
                    "tax_ids": [self.tax_iva16.id],
                }
            ]
        )
        
        self.invoice.invoice_date_due = datetime.now() - timedelta(days=1)

        with self.assertRaises(UserError) as e:        
            self.invoice.generate_document_digital()
            _logger.info(e.exception)
        _logger.info("Test passed: Invalid expiration date validation")

    # # Factura con Sucursal
    # @patch('odoo.addons.l10n_ve_invoice_digital.models.account_move.AccountMove.call_tfhka_api', side_effect=mock_api)
    # def test_17_generate_document_digital_subsidiary_succes(self, mock_call):
    #     self.company.write({"subsidiary": True})
    #     subsidiary = self._create_subsidiary()

    #     self.invoice = self._create_invoice(
    #         products=[
    #             {
    #                 "product_id": self.product.id,
    #                 "price_unit": 1,
    #                 "tax_ids": [self.tax_iva16.id],
    #             }
    #         ]
    #     )
    #     self.invoice.account_analytic_id = subsidiary.id

    #     self.invoice.generate_document_digital()
    #     self.assertEqual(self.invoice.is_digitalized, True)
    #     _logger.info("Test passed: Digital document with subsidiary successfully generated.")

    # # Validacion Sucursales
    # @patch('odoo.addons.l10n_ve_invoice_digital.models.account_move.AccountMove.call_tfhka_api', side_effect=mock_api)
    # def test_18_generate_document_digital_validation_subsidiary_error(self, mock_call):
    #     self.company.write({"subsidiary": True})
    #     subsidiary = self._create_subsidiary()
    #     subsidiary.code = ""
    #     self.invoice = self._create_invoice(
    #         products=[
    #             {
    #                 "product_id": self.product.id,
    #                 "price_unit": 1,
    #                 "tax_ids": [self.tax_iva16.id],
    #             }
    #         ]
    #     )
    #     self.invoice.account_analytic_id = subsidiary.id

    #     with self.assertRaises(UserError) as e:        
    #         self.invoice.generate_document_digital()
    #         _logger.info(e.exception)
    #     _logger.info("Test passed: Invalid branch configuration validation")
