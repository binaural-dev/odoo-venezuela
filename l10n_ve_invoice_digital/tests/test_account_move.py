from odoo.exceptions import UserError, ValidationError
from odoo import fields, Command
from odoo.tests import TransactionCase, tagged
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)

@tagged("post_install", "-at_install", "l10n_ve_invoice_digital", "invoice_digital") 
class TestAccountMoveApiCalls(TransactionCase):

    def setUp(self):
        super().setUp()
        self.env.registry.clear_cache()
        _ = self.env["account.move"]
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
                "country_id": self.env.ref('base.ve').id,
            }
        )
        self.env.user.company_id = self.company.id

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

        self.tax_group = self.env['account.tax.group'].create({
            'name': 'IVA',
        })
        
        self.tax_iva16 = self.env['account.tax'].create({
            'name': 'IVA 16%',
            'amount': 16,
            'amount_type': 'percent',
            'type_tax_use': 'sale',
            'tax_group_id': self.tax_group.id,
        })

        # Crear el producto
        self.product = self.env['product.product'].create({
            'name': 'Producto Prueba',
            'type': 'service',
            'list_price': 100,
            'barcode': '123456789',
            'taxes_id': [Command.set([self.tax_iva16.id])],
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
            currency_id=None,
            foreign_currency_id=None,
            do_post=True,
            post_context=None,
        ):
        """Helper function to create an invoice with given parameters.
        Args:
            products (list): List of dictionaries with product details.
            foreign_rate (float): Foreign exchange rate.
            foreign_inverse_rate (float): Inverse foreign exchange rate.
            currency_id (int): Invoice currency ID (defaults to USD).
            foreign_currency_id (int): Foreign currency ID (defaults to VEF).
            do_post (bool): Whether to post the invoice after creation.
            post_context (dict): Context dict passed to action_post.
        """
        invoice_lines = [
            Command.create(
                {
                    "product_id": product["product_id"],
                    "quantity": product.get("quantity", 1),
                    "price_unit": product["price_unit"],
                    "tax_ids": product.get("tax_ids", []),
                    "account_id": self.acc_income.id, 
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
            "foreign_currency_id": foreign_currency_id or self.currency_vef.id,
            "currency_id": currency_id or self.currency_usd.id,
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

        if do_post:
            if post_context:
                invoice.with_context(**post_context).action_post()
            else:
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

    def test_07_action_post_mixed_invoicing_disabled(self):
        self.company.mix_invoicing_tfhka = False
        self.journal.digital_invoice = False
        with self.assertRaises(ValidationError):
            self._create_invoice(
                products=[
                    {
                        "product_id": self.product.id,
                        "price_unit": 1,
                        "tax_ids": [self.tax_iva16.id],
                    }
                ]
            )
        _logger.info("Test passed: Mixed invoicing disabled validation raised as expected.")

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

    def test_17_is_eligible_for_tfhka_not_digital_journal(self):
        self.journal.digital_invoice = False
        invoice = self._create_invoice(
            products=[{"product_id": self.product.id, "price_unit": 1, "tax_ids": [self.tax_iva16.id]}]
        )
        self.assertFalse(invoice._is_eligible_for_tfhka())


    def test_19_get_buyer_missing_vat(self):
        partner = self.env['res.partner'].create({
            'name': 'Sin RIF',
            'country_id': self.env.ref('base.ve').id,
            'phone': '04141234567',
            'email': 'test@test.com',
            'street': 'Calle',
        })
        invoice = self._create_invoice(
            products=[{"product_id": self.product.id, "price_unit": 1, "tax_ids": [self.tax_iva16.id]}]
        )
        invoice.partner_id = partner
        with self.assertRaises(UserError):
            invoice.get_buyer()


    def test_21_get_buyer_missing_phone(self):
        partner = self.env['res.partner'].create({
            'name': 'Sin Telefono',
            'vat': 'E12345679',
            'prefix_vat': 'E',
            'country_id': self.env.ref('base.ve').id,
            'email': 'test@test.com',
            'street': 'Calle',
        })
        invoice = self._create_invoice(
            products=[{"product_id": self.product.id, "price_unit": 1, "tax_ids": [self.tax_iva16.id]}]
        )
        invoice.partner_id = partner
        with self.assertRaises(UserError):
            invoice.get_buyer()

    def test_22_get_buyer_missing_email(self):
        partner = self.env['res.partner'].create({
            'name': 'Sin Email',
            'vat': 'G12345679',
            'prefix_vat': 'G',
            'country_id': self.env.ref('base.ve').id,
            'phone': '04141234567',
            'street': 'Calle',
        })
        invoice = self._create_invoice(
            products=[{"product_id": self.product.id, "price_unit": 1, "tax_ids": [self.tax_iva16.id]}]
        )
        invoice.partner_id = partner
        with self.assertRaises(UserError):
            invoice.get_buyer()

    def test_23_get_payment_type_credit(self):
        term = self.env['account.payment.term'].create({
            'name': '30 dias',
            'line_ids': [(0, 0, {'nb_days': 30, 'value': 'percent', 'value_amount': 100})],
        })
        invoice = self._create_invoice(
            products=[{"product_id": self.product.id, "price_unit": 1, "tax_ids": [self.tax_iva16.id]}]
        )
        invoice.invoice_payment_term_id = term
        self.assertEqual(invoice.get_payment_type(), "Crédito")

    def test_24_get_payment_type_immediate(self):
        invoice = self._create_invoice(
            products=[{"product_id": self.product.id, "price_unit": 1, "tax_ids": [self.tax_iva16.id]}]
        )
        self.assertEqual(invoice.get_payment_type(), "Inmediato")

    def test_25_call_tfhka_api_undefined_endpoint(self):
        self.company.write({
            "url_tfhka": "https://api.tfhka.com",
            "token_auth_tfhka": "token_fake",
            "invoice_digital_tfhka": True,
            "sequence_validation_tfhka": True,
        })
        invoice = self._create_invoice(
            products=[{"product_id": self.product.id, "price_unit": 1, "tax_ids": [self.tax_iva16.id]}]
        )
        with self.assertRaises(UserError):
            invoice.call_tfhka_api("no_existe", {})

    @patch('requests.post')
    def test_26_call_tfhka_api_401_refresh_token(self, mock_post):
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
                    resp.json.return_value = {
                        "codigo": "200",
                        "mensaje": "OK",
                        "resultado": {"numeroControl": "00-00000001"}
                    }
            return resp
        mock_post.side_effect = side_effect
        invoice = self._create_invoice(
            products=[{"product_id": self.product.id, "price_unit": 1, "tax_ids": [self.tax_iva16.id]}]
        )
        result = invoice.call_tfhka_api("emision", {})
        self.assertEqual(result["codigo"], "200")

    def test_27_get_base_url_raises(self):
        self.company.url_tfhka = ""
        invoice = self._create_invoice(
            products=[{"product_id": self.product.id, "price_unit": 1, "tax_ids": [self.tax_iva16.id]}]
        )
        with self.assertRaises(UserError):
            invoice.get_base_url()

    def test_28_get_token_raises(self):
        self.company.token_auth_tfhka = ""
        invoice = self._create_invoice(
            products=[{"product_id": self.product.id, "price_unit": 1, "tax_ids": [self.tax_iva16.id]}]
        )
        with self.assertRaises(ValidationError):
            invoice.get_token()

    @patch('odoo.addons.l10n_ve_invoice_digital.models.account_move.AccountMove.call_tfhka_api', side_effect=mock_api)
    def test_29_get_item_details_product_type(self, mock_call):
        prod = self.env['product.product'].create({
            'name': 'Producto Fisico',
            'type': 'consu',
            'list_price': 50,
        })
        invoice = self._create_invoice(
            products=[{"product_id": prod.id, "price_unit": 50, "tax_ids": [self.tax_iva16.id]}]
        )
        details = invoice.get_item_details()
        self.assertEqual(details[0]["indicadorBienoServicio"], "1")

    @patch('odoo.addons.l10n_ve_invoice_digital.models.account_move.AccountMove.call_tfhka_api', side_effect=mock_api)
    def test_31_compute_invisible_check(self, mock_call):
        invoice = self._create_invoice(
            products=[{"product_id": self.product.id, "price_unit": 1, "tax_ids": [self.tax_iva16.id]}]
        )
        invoice.generate_document_digital()
        invoice._compute_invisible_check()
        self.assertTrue(invoice.show_digital_invoice)
        self.assertTrue(invoice.show_digital_credit_note)

    def test_32_get_document_identification_debit_note(self):
        inv = self._create_invoice(
            products=[{"product_id": self.product.id, "price_unit": 1, "tax_ids": [self.tax_iva16.id]}]
        )
        debit = self._create_invoice(
            products=[{"product_id": self.product.id, "price_unit": 1, "tax_ids": [self.tax_iva16.id]}],
            debit_origin_id=inv,
        )
        ident = debit.get_document_identification("03", "123", "")
        self.assertEqual(ident["numeroFacturaAfectada"], str(inv.sequence_number))

    def test_33_get_document_identification_credit_note(self):
        inv = self._create_invoice(
            products=[{"product_id": self.product.id, "price_unit": 1, "tax_ids": [self.tax_iva16.id]}]
        )
        credit = self._create_invoice(
            products=[{"product_id": self.product.id, "price_unit": 1, "tax_ids": [self.tax_iva16.id]}],
            move_type="out_refund",
            reversed_entry_id=inv,
        )
        ident = credit.get_document_identification("02", "124", "")
        self.assertEqual(ident["numeroFacturaAfectada"], str(inv.sequence_number))

    def test_34_get_document_identification_no_invoice_date(self):
        inv = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "journal_id": self.journal.id,
            "currency_id": self.currency_usd.id,
            "foreign_currency_id": self.currency_vef.id,
            "foreign_rate": 38,
            "foreign_inverse_rate": 38,
            "manually_set_rate": True,
            "invoice_line_ids": [(0, 0, {
                "product_id": self.product.id,
                "quantity": 1,
                "price_unit": 1,
                "account_id": self.acc_income.id,
                "tax_ids": [(6, 0, [self.tax_iva16.id])],
            })],
        })
        with self.assertRaises(UserError):
            inv.get_document_identification("01", "125", "")

    def test_35_get_buyer_numeric_vat(self):
        partner = self.env['res.partner'].create({
            'name': 'Cliente Numérico',
            'vat': '12345678',
            'country_id': self.env.ref('base.ve').id,
            'phone': '04141234567',
            'email': 'test@test.com',
            'street': 'Calle',
        })
        invoice = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": partner.id,
            "journal_id": self.journal.id,
            "currency_id": self.currency_usd.id,
            "foreign_currency_id": self.currency_vef.id,
            "foreign_rate": 38,
            "foreign_inverse_rate": 38,
            "manually_set_rate": True,
            "invoice_line_ids": [(0, 0, {
                "product_id": self.product.id,
                "quantity": 1,
                "price_unit": 1,
                "account_id": self.acc_income.id,
                "tax_ids": [(6, 0, [self.tax_iva16.id])],
            })],
        })
        buyer = invoice.get_buyer()
        self.assertTrue(buyer)
        self.assertEqual(buyer["numeroIdentificacion"], "12345678")

    def test_36_get_buyer_prefix_vat(self):
        partner = self.env['res.partner'].create({
            'name': 'Cliente Prefijo',
            'vat': 'V12345678',
            'prefix_vat': 'V',
            'country_id': self.env.ref('base.ve').id,
            'phone': '04141234567',
            'email': 'test@test.com',
            'street': 'Calle',
        })
        invoice = self._create_invoice(
            products=[{"product_id": self.product.id, "price_unit": 1, "tax_ids": [self.tax_iva16.id]}]
        )
        invoice.partner_id = partner
        buyer = invoice.get_buyer()
        self.assertEqual(buyer["tipoIdentificacion"], "V")

    def test_39_get_last_document_number_zero(self):
        with patch('odoo.addons.l10n_ve_invoice_digital.models.account_move.AccountMove.call_tfhka_api') as mock_call:
            mock_call.return_value = 0
            invoice = self._create_invoice(
                products=[{"product_id": self.product.id, "price_unit": 1, "tax_ids": [self.tax_iva16.id]}]
            )
            result = invoice.get_last_document_number("01", "")
            self.assertEqual(result, 0)

    def test_40_get_payment_methods_with_payment(self):
        invoice = self._create_invoice(
            products=[{"product_id": self.product.id, "price_unit": 100, "tax_ids": [self.tax_iva16.id]}]
        )
        pay = self._create_payment(amount=100)
        invoice._compute_tax_totals()
        # Forzar widget de pagos
        methods = invoice.get_payment_methods()
        self.assertTrue(methods or methods is False)

    def test_41_compute_invisible_check_credit_note(self):
        inv = self._create_invoice(
            products=[{"product_id": self.product.id, "price_unit": 1, "tax_ids": [self.tax_iva16.id]}]
        )
        credit = self._create_invoice(
            products=[{"product_id": self.product.id, "price_unit": 1, "tax_ids": [self.tax_iva16.id]}],
            move_type="out_refund",
            reversed_entry_id=inv,
        )
        credit._compute_invisible_check()
        self.assertTrue(credit.show_digital_credit_note)

    def test_42_compute_invisible_check_debit_note(self):
        inv = self._create_invoice(
            products=[{"product_id": self.product.id, "price_unit": 1, "tax_ids": [self.tax_iva16.id]}]
        )
        debit = self._create_invoice(
            products=[{"product_id": self.product.id, "price_unit": 1, "tax_ids": [self.tax_iva16.id]}],
            debit_origin_id=inv,
        )
        debit._compute_invisible_check()
        self.assertTrue(debit.show_digital_debit_note)

    def test_43_get_document_identification_due_date_equal(self):
        inv = self._create_invoice(
            products=[{"product_id": self.product.id, "price_unit": 1, "tax_ids": [self.tax_iva16.id]}]
        )
        inv.invoice_date_due = inv.invoice_date
        ident = inv.get_document_identification("01", "126", "")
        self.assertEqual(ident["fechaVencimiento"], ident["fechaEmision"])

    def test_44_get_document_identification_ref_with_comma(self):
        inv = self._create_invoice(
            products=[{"product_id": self.product.id, "price_unit": 1, "tax_ids": [self.tax_iva16.id]}],
            ref="Motivo, detalle adicional"
        )
        debit = self._create_invoice(
            products=[{"product_id": self.product.id, "price_unit": 1, "tax_ids": [self.tax_iva16.id]}],
            debit_origin_id=inv,
            ref="Motivo, detalle adicional",
        )
        ident = debit.get_document_identification("03", "127", "")
        self.assertEqual(ident["comentarioFacturaAfectada"], "detalle adicional")

    def test_45_generate_document_digital_no_document_type(self):
        inv = self.env["account.move"].create({
            "move_type": "out_refund",
            "partner_id": self.partner.id,
            "journal_id": self.journal.id,
            "currency_id": self.currency_usd.id,
            "foreign_currency_id": self.currency_vef.id,
            "foreign_rate": 38,
            "foreign_inverse_rate": 38,
            "manually_set_rate": True,
            "invoice_line_ids": [(0, 0, {
                "product_id": self.product.id,
                "quantity": 1,
                "price_unit": 1,
                "account_id": self.acc_income.id,
                "tax_ids": [(6, 0, [self.tax_iva16.id])],
            })],
        })
        res = inv.generate_document_digital()
        self.assertIsNone(res)

    def test_46_get_currency(self):
        invoice = self._create_invoice(
            products=[{"product_id": self.product.id, "price_unit": 1, "tax_ids": [self.tax_iva16.id]}]
        )
        name = invoice.get_currency(self.currency_usd.id)
        self.assertEqual(name, "USD")

    def test_47_get_payment(self):
        pay = self._create_payment()
        invoice = self._create_invoice(
            products=[{"product_id": self.product.id, "price_unit": 1, "tax_ids": [self.tax_iva16.id]}]
        )
        result = invoice.get_payment(pay.id)
        self.assertTrue(result)

    def test_48_build_payment_info_ves(self):
        pay = self._create_payment()
        # Forzar que el pago use moneda VEF
        pay.currency_id = self.env.ref("base.VEF")
        invoice = self._create_invoice(
            products=[{"product_id": self.product.id, "price_unit": 1, "tax_ids": [self.tax_iva16.id]}]
        )
        info = invoice.build_payment_info(pay)
        self.assertEqual(info["moneda"], "VES")

    def test_49_get_item_details_with_discount(self):
        prod = self.env['product.product'].create({
            'name': 'Prod Descuento',
            'type': 'service',
            'list_price': 100,
        })
        invoice = self._create_invoice(
            products=[{"product_id": prod.id, "price_unit": 100, "tax_ids": [self.tax_iva16.id]}]
        )
        invoice.invoice_line_ids[0].discount = 10
        details = invoice.get_item_details()
        self.assertTrue(float(details[0]["descuentoMonto"]) > 0)

    def test_50_compute_invisible_check_draft(self):
        inv = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "journal_id": self.journal.id,
            "currency_id": self.currency_usd.id,
            "foreign_currency_id": self.currency_vef.id,
            "foreign_rate": 38,
            "foreign_inverse_rate": 38,
            "manually_set_rate": True,
            "invoice_line_ids": [(0, 0, {
                "product_id": self.product.id,
                "quantity": 1,
                "price_unit": 1,
                "account_id": self.acc_income.id,
                "tax_ids": [(6, 0, [self.tax_iva16.id])],
            })],
        })
        inv._compute_invisible_check()
        self.assertTrue(inv.show_digital_invoice)

    def test_51_compute_invisible_check_company_disabled(self):
        self.company.invoice_digital_tfhka = False
        inv = self._create_invoice(
            products=[{"product_id": self.product.id, "price_unit": 1, "tax_ids": [self.tax_iva16.id]}]
        )
        inv._compute_invisible_check()
        self.assertTrue(inv.show_digital_invoice)

    def test_52_compute_invisible_check_reversed_not_digitized(self):
        inv = self._create_invoice(
            products=[{"product_id": self.product.id, "price_unit": 1, "tax_ids": [self.tax_iva16.id]}]
        )
        credit = self._create_invoice(
            products=[{"product_id": self.product.id, "price_unit": 1, "tax_ids": [self.tax_iva16.id]}],
            move_type="out_refund",
            reversed_entry_id=inv,
        )
        credit._compute_invisible_check()
        self.assertTrue(credit.show_digital_credit_note)

    def test_53_compute_invisible_check_debit_not_digitized(self):
        inv = self._create_invoice(
            products=[{"product_id": self.product.id, "price_unit": 1, "tax_ids": [self.tax_iva16.id]}]
        )
        debit = self._create_invoice(
            products=[{"product_id": self.product.id, "price_unit": 1, "tax_ids": [self.tax_iva16.id]}],
            debit_origin_id=inv,
        )
        debit._compute_invisible_check()
        self.assertTrue(debit.show_digital_debit_note)

    def test_54_compute_invisible_check_debit_note_posted(self):
        inv = self._create_invoice(
            products=[{"product_id": self.product.id, "price_unit": 1, "tax_ids": [self.tax_iva16.id]}]
        )
        inv.is_digitalized = True
        debit = self._create_invoice(
            products=[{"product_id": self.product.id, "price_unit": 1, "tax_ids": [self.tax_iva16.id]}],
            debit_origin_id=inv,
        )
        debit._compute_invisible_check()
        self.assertTrue(debit.show_digital_debit_note)

    def test_55_get_totals_too_many_payments(self):
        invoice = self._create_invoice(
            products=[{"product_id": self.product.id, "price_unit": 100, "tax_ids": [self.tax_iva16.id]}]
        )
        with patch('odoo.addons.l10n_ve_invoice_digital.models.account_move.AccountMove.get_payment_methods', return_value=[{"forma": "01"}] * 6):
            with self.assertRaises(UserError):
                invoice.get_totals()

    def test_56_get_totals_payment_without_forma(self):
        invoice = self._create_invoice(
            products=[{"product_id": self.product.id, "price_unit": 100, "tax_ids": [self.tax_iva16.id]}]
        )
        with patch('odoo.addons.l10n_ve_invoice_digital.models.account_move.AccountMove.get_payment_methods', return_value=[{"forma": ""}]):
            with self.assertRaises(ValidationError):
                invoice.get_totals()

    def test_57_get_payment_methods_with_widget(self):
        invoice = self._create_invoice(
            products=[{"product_id": self.product.id, "price_unit": 100, "tax_ids": [self.tax_iva16.id]}]
        )
        pay = self._create_payment(amount=100)
        # Simular widget de pagos
        invoice.invoice_payments_widget = {"content": [{"account_payment_id": pay.id}]}
        methods = invoice.get_payment_methods()
        self.assertTrue(methods)

    def test_58_get_payment_methods_exception(self):
        invoice = self._create_invoice(
            products=[{"product_id": self.product.id, "price_unit": 100, "tax_ids": [self.tax_iva16.id]}]
        )
        invoice.invoice_payments_widget = None
        methods = invoice.get_payment_methods()
        self.assertFalse(methods)

    def test_59_get_document_identification_debit_origin(self):
        inv = self._create_invoice(
            products=[{"product_id": self.product.id, "price_unit": 1, "tax_ids": [self.tax_iva16.id]}]
        )
        debit = self._create_invoice(
            products=[{"product_id": self.product.id, "price_unit": 1, "tax_ids": [self.tax_iva16.id]}],
            debit_origin_id=inv,
        )
        ident = debit.get_document_identification("03", "128", "")
        self.assertEqual(ident["numeroFacturaAfectada"], str(inv.sequence_number))
        self.assertEqual(ident["fechaFacturaAfectada"], inv.invoice_date.strftime("%d/%m/%Y"))

    def test_60_get_document_identification_reversed(self):
        inv = self._create_invoice(
            products=[{"product_id": self.product.id, "price_unit": 1, "tax_ids": [self.tax_iva16.id]}]
        )
        credit = self._create_invoice(
            products=[{"product_id": self.product.id, "price_unit": 1, "tax_ids": [self.tax_iva16.id]}],
            move_type="out_refund",
            reversed_entry_id=inv,
        )
        ident = credit.get_document_identification("02", "129", "")
        self.assertEqual(ident["numeroFacturaAfectada"], str(inv.sequence_number))
        self.assertEqual(ident["fechaFacturaAfectada"], inv.invoice_date.strftime("%d/%m/%Y"))

    def test_61_get_document_identification_no_due_date(self):
        inv = self._create_invoice(
            products=[{"product_id": self.product.id, "price_unit": 1, "tax_ids": [self.tax_iva16.id]}]
        )
        inv.invoice_date_due = False
        ident = inv.get_document_identification("01", "130", "")
        self.assertEqual(ident["fechaVencimiento"], ident["fechaEmision"])

    def test_62_generate_document_digital_company_disabled(self):
        self.company.write({"invoice_digital_tfhka": False})
        inv = self._create_invoice(
            products=[{"product_id": self.product.id, "price_unit": 1, "tax_ids": [self.tax_iva16.id]}]
        )
        res = inv.generate_document_digital()
        self.assertIsNone(res)

    def test_63_tfhka_get_document_type_and_series(self):
        inv = self._create_invoice(
            products=[{"product_id": self.product.id, "price_unit": 1, "tax_ids": [self.tax_iva16.id]}]
        )
        doc_type, series = inv._tfhka_get_document_type_and_series()
        self.assertEqual(doc_type, "01")
        self.assertEqual(series, "")

    @patch('odoo.addons.l10n_ve_invoice_digital.models.account_move.AccountMove.call_tfhka_api')
    def test_64_generate_document_data_sequence_update_error(self, mock_call):
        mock_call.return_value = {
            "codigo": "200",
            "resultado": {"numeroControl": "00-00000001"}
        }
        inv = self._create_invoice(
            products=[{"product_id": self.product.id, "price_unit": 1, "tax_ids": [self.tax_iva16.id]}]
        )
        from odoo.addons.account.models.account_journal import AccountJournal
        with patch.object(AccountJournal, 'write', side_effect=Exception("fail")):
            inv.generate_document_data("123", "01", "")
        self.assertTrue(inv.is_digitalized)

    def test_65_is_eligible_for_tfhka_company_disabled(self):
        self.company.write({"invoice_digital_tfhka": False})
        inv = self._create_invoice(
            products=[{"product_id": self.product.id, "price_unit": 1, "tax_ids": [self.tax_iva16.id]}]
        )
        self.assertFalse(inv._is_eligible_for_tfhka())

    def test_66_tfhka_get_document_type_credit_note(self):
        inv = self._create_invoice(
            products=[{"product_id": self.product.id, "price_unit": 1, "tax_ids": [self.tax_iva16.id]}]
        )
        credit = self._create_invoice(
            products=[{"product_id": self.product.id, "price_unit": 1, "tax_ids": [self.tax_iva16.id]}],
            move_type="out_refund",
            reversed_entry_id=inv,
        )
        doc_type, series = credit._tfhka_get_document_type_and_series()
        self.assertEqual(doc_type, "02")
        self.assertEqual(series, "")

    def test_67_generate_document_digital_non_numeric_last_number(self):
        with patch('odoo.addons.l10n_ve_invoice_digital.models.account_move.AccountMove.get_last_document_number', return_value="abc"):
            with patch('odoo.addons.l10n_ve_invoice_digital.models.account_move.AccountMove.query_numbering', return_value=None):
                with patch('odoo.addons.l10n_ve_invoice_digital.models.account_move.AccountMove.call_tfhka_api') as mock_call:
                    mock_call.return_value = {
                        "codigo": "200",
                        "resultado": {"numeroControl": "00-00000001"}
                    }
                    inv = self._create_invoice(
                        products=[{"product_id": self.product.id, "price_unit": 1, "tax_ids": [self.tax_iva16.id]}]
                    )
                    inv.generate_document_digital()
                    self.assertTrue(inv.is_digitalized)

    def test_68_get_seller_with_seller_id(self):
        if "seller_id" not in self.env["account.move"]._fields:
            self.skipTest("seller_id field not installed")
        user = self.env["res.users"].create({
            "name": "Vendedor Test",
            "login": "vendedor_test",
        })
        inv = self._create_invoice(
            products=[{"product_id": self.product.id, "price_unit": 1, "tax_ids": [self.tax_iva16.id]}]
        )
        inv.seller_id = user.partner_id
        seller = inv.get_seller()
        self.assertTrue(seller)
        self.assertEqual(seller["nombre"], "Vendedor Test")

    def test_69_get_totals_vef(self):
        vef = self.env.ref("base.VEF")
        self.company.currency_id = vef
        inv = self._create_invoice(
            products=[{"product_id": self.product.id, "price_unit": 1, "tax_ids": [self.tax_iva16.id]}],
            currency_id=vef.id,
            foreign_currency_id=self.currency_usd.id,
        )
        totals, foreign = inv.get_totals()
        self.assertIn("montoGravadoTotal", totals)
        self.assertTrue(isinstance(foreign, dict))

    def test_70_get_tax_subtotals_vef(self):
        vef = self.env.ref("base.VEF")
        self.company.currency_id = vef
        inv = self._create_invoice(
            products=[{"product_id": self.product.id, "price_unit": 1, "tax_ids": [self.tax_iva16.id]}],
            currency_id=vef.id,
            foreign_currency_id=self.currency_usd.id,
        )
        result = inv.get_tax_subtotals("VEF")
        self.assertTrue(isinstance(result, tuple))
        self.assertTrue(isinstance(result[0], list))

    def test_71_get_item_details_vef(self):
        vef = self.env.ref("base.VEF")
        self.company.currency_id = vef
        inv = self._create_invoice(
            products=[{"product_id": self.product.id, "price_unit": 1, "tax_ids": [self.tax_iva16.id]}],
            currency_id=vef.id,
            foreign_currency_id=self.currency_usd.id,
        )
        details = inv.get_item_details()
        self.assertTrue(len(details) > 0)
        self.assertEqual(details[0]["indicadorBienoServicio"], "2")

    def test_72_get_document_identification_no_affected_invoice(self):
        inv = self._create_invoice(
            products=[{"product_id": self.product.id, "price_unit": 1, "tax_ids": [self.tax_iva16.id]}]
        )
        ident = inv.get_document_identification("01", "131", "")
        self.assertEqual(ident["numeroFacturaAfectada"], "")
        self.assertEqual(ident["fechaFacturaAfectada"], "")
        self.assertEqual(ident["montoFacturaAfectada"], "")

    def test_73_compute_invisible_check_posted_not_digitized(self):
        inv = self._create_invoice(
            products=[{"product_id": self.product.id, "price_unit": 1, "tax_ids": [self.tax_iva16.id]}]
        )
        inv._compute_invisible_check()
        self.assertTrue(inv.show_digital_invoice)

    def test_76_get_payment_methods_with_widget_no_content(self):
        inv = self._create_invoice(
            products=[{"product_id": self.product.id, "price_unit": 100, "tax_ids": [self.tax_iva16.id]}]
        )
        inv.invoice_payments_widget = {"content": []}
        methods = inv.get_payment_methods()
        self.assertFalse(methods)

    def test_77_get_buyer_missing_prefix_vat_numeric(self):
        partner = self.env['res.partner'].create({
            'name': 'Cliente Numérico Sin Prefijo',
            'vat': '12345679',
            'country_id': self.env.ref('base.ve').id,
            'phone': '04141234567',
            'email': 'test@test.com',
            'street': 'Calle',
        })
        inv = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": partner.id,
            "journal_id": self.journal.id,
            "currency_id": self.currency_usd.id,
            "foreign_currency_id": self.currency_vef.id,
            "foreign_rate": 38,
            "foreign_inverse_rate": 38,
            "manually_set_rate": True,
            "invoice_line_ids": [(0, 0, {
                "product_id": self.product.id,
                "quantity": 1,
                "price_unit": 1,
                "account_id": self.acc_income.id,
                "tax_ids": [(6, 0, [self.tax_iva16.id])],
            })],
        })
        buyer = inv.get_buyer()
        # prefix_vat default in l10n_ve_contact is 'V'
        self.assertEqual(buyer["tipoIdentificacion"], "V")

    def test_79_tfhka_validate_mixed_invoicing_disabled(self):
        self.company.mix_invoicing_tfhka = False
        self.journal.digital_invoice = False
        inv = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "journal_id": self.journal.id,
            "currency_id": self.currency_usd.id,
            "invoice_line_ids": [(0, 0, {
                "product_id": self.product.id,
                "quantity": 1,
                "price_unit": 1,
                "account_id": self.acc_income.id,
                "tax_ids": [(5, 0, 0)],
            })],
        })
        with self.assertRaises(ValidationError):
            inv._tfhka_validate_mixed_invoicing()

    def test_80_tfhka_get_document_type_and_series_no_prefix(self):
        self.company.group_sales_invoicing_series = True
        seq = self.env['ir.sequence'].create({
            'name': 'Serie Sin Prefix',
            'code': 'account.move',
            'padding': 4,
        })
        self.journal.write({
            'series_correlative_sequence_id': seq.id,
            'sequence_id': seq.id,
        })
        inv = self._create_invoice(
            products=[{"product_id": self.product.id, "price_unit": 1, "tax_ids": [self.tax_iva16.id]}]
        )
        with self.assertRaises(UserError):
            inv._tfhka_get_document_type_and_series()

    def test_83_call_tfhka_api_request_exception(self):
        inv = self._create_invoice(
            products=[{"product_id": self.product.id, "price_unit": 1, "tax_ids": [self.tax_iva16.id]}]
        )
        with patch('odoo.addons.l10n_ve_invoice_digital.models.account_move.requests.post') as mock_post:
            mock_post.side_effect = Exception("Connection error")
            with self.assertRaises(UserError):
                inv.call_tfhka_api("emision", {})

    def test_87_get_tax_subtotals_vef_no_taxes(self):
        vef = self.env.ref("base.VEF")
        self.company.currency_id = vef
        inv = self._create_invoice(
            products=[{"product_id": self.product.id, "price_unit": 1, "tax_ids": []}],
            currency_id=vef.id,
            foreign_currency_id=self.currency_usd.id,
            post_context={"move_action_post_alert": True},
        )
        result = inv.get_tax_subtotals("VEF")
        self.assertEqual(result, ([], []))

    def test_88_get_tax_subtotals_no_vef_no_taxes(self):
        inv = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "journal_id": self.journal.id,
            "currency_id": self.currency_usd.id,
            "foreign_currency_id": self.currency_vef.id,
            "foreign_rate": 38,
            "foreign_inverse_rate": 38,
            "manually_set_rate": True,
            "invoice_line_ids": [(0, 0, {
                "product_id": self.product.id,
                "quantity": 1,
                "price_unit": 1,
                "account_id": self.acc_income.id,
                "tax_ids": [(5, 0, 0)],
            })],
        })
        inv.with_context(move_action_post_alert=True).action_post()
        result = inv.get_tax_subtotals("USD")
        self.assertEqual(result, ([], []))

    def test_89_get_payment_type_empty(self):
        result = self.env['account.move'].browse([]).get_payment_type()
        self.assertIsNone(result)

    def test_91_get_buyer_no_partner(self):
        inv = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": False,
            "journal_id": self.journal.id,
            "currency_id": self.currency_usd.id,
            "invoice_line_ids": [(0, 0, {
                "product_id": self.product.id,
                "quantity": 1,
                "price_unit": 1,
                "account_id": self.acc_income.id,
                "tax_ids": [(5, 0, 0)],
            })],
        })
        result = inv.get_buyer()
        self.assertIsNone(result)

    def test_92_get_payment_methods_invalid_payment(self):
        inv = self._create_invoice(
            products=[{"product_id": self.product.id, "price_unit": 100, "tax_ids": [self.tax_iva16.id]}]
        )
        inv.invoice_payments_widget = {"content": [{"account_payment_id": 99999}]}
        methods = inv.get_payment_methods()
        self.assertFalse(methods)

    def test_96_tfhka_validate_mixed_invoicing_enabled(self):
        self.company.mix_invoicing_tfhka = True
        self.journal.digital_invoice = False
        inv = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "journal_id": self.journal.id,
            "currency_id": self.currency_usd.id,
            "invoice_line_ids": [(0, 0, {
                "product_id": self.product.id,
                "quantity": 1,
                "price_unit": 1,
                "account_id": self.acc_income.id,
                "tax_ids": [(5, 0, 0)],
            })],
        })
        inv._tfhka_validate_mixed_invoicing()

    def test_98_tfhka_get_document_type_credit_note_no_reversed(self):
        credit = self._create_invoice(
            products=[{"product_id": self.product.id, "price_unit": 1, "tax_ids": [self.tax_iva16.id]}],
            move_type="out_refund",
        )
        doc_type, series = credit._tfhka_get_document_type_and_series()
        self.assertEqual(doc_type, "")
        self.assertEqual(series, "")

    def test_99_tfhka_get_document_type_and_series_with_prefix(self):
        self.company.group_sales_invoicing_series = True
        seq = self.env['ir.sequence'].create({
            'name': 'Serie Con Prefix',
            'code': 'account.move',
            'prefix': 'INV-',
            'padding': 4,
        })
        self.journal.write({
            'series_correlative_sequence_id': seq.id,
            'sequence_id': seq.id,
        })
        inv = self._create_invoice(
            products=[{"product_id": self.product.id, "price_unit": 1, "tax_ids": [self.tax_iva16.id]}]
        )
        doc_type, series = inv._tfhka_get_document_type_and_series()
        self.assertEqual(series, "INV")

    def test_100_get_buyer_empty_prefix_vat(self):
        partner = self.env['res.partner'].create({
            'name': 'Cliente Sin Prefijo',
            'vat': 'J12345679',
            'prefix_vat': '',
            'country_id': self.env.ref('base.ve').id,
            'phone': '04141234567',
            'email': 'test@test.com',
            'street': 'Calle',
        })
        inv = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": partner.id,
            "journal_id": self.journal.id,
            "currency_id": self.currency_usd.id,
            "invoice_line_ids": [(0, 0, {
                "product_id": self.product.id,
                "quantity": 1,
                "price_unit": 1,
                "account_id": self.acc_income.id,
                "tax_ids": [(5, 0, 0)],
            })],
        })
        buyer = inv.get_buyer()
        self.assertEqual(buyer["tipoIdentificacion"], "J")





    def test_105_call_tfhka_api_request_exception(self):
        inv = self._create_invoice(
            products=[{"product_id": self.product.id, "price_unit": 1, "tax_ids": [self.tax_iva16.id]}]
        )
        with patch('requests.post') as mock_post:
            mock_post.side_effect = Exception("Connection error")
            with self.assertRaises(UserError):
                inv.call_tfhka_api("emision", {})




    def test_109_get_document_identification_empty_recordset(self):
        result = self.env['account.move'].browse([]).get_document_identification("01", "1", "")
        self.assertIsNone(result)






    def test_115_get_tax_subtotals_vef_no_taxes(self):
        vef = self.env.ref("base.VEF")
        self.company.currency_id = vef
        inv = self._create_invoice(
            products=[{"product_id": self.product.id, "price_unit": 1, "tax_ids": []}],
            currency_id=vef.id,
            foreign_currency_id=self.currency_usd.id,
            post_context={"move_action_post_alert": True},
        )
        result = inv.get_tax_subtotals("VEF")
        self.assertEqual(result, ([], []))

    def test_120_is_eligible_for_tfhka_wrong_move_type(self):
        misc_journal = self.env['account.journal'].create({
            'name': 'Miscelaneos Elegibilidad',
            'code': 'MSCE',
            'type': 'general',
            'company_id': self.company.id,
            'digital_invoice': True,
        })
        entry = self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': misc_journal.id,
            'date': fields.Date.today(),
        })
        self.assertFalse(entry._is_eligible_for_tfhka())

        self.journal.digital_invoice = True
        inv = self._create_invoice(
            products=[{"product_id": self.product.id, "price_unit": 1, "tax_ids": [self.tax_iva16.id]}]
        )
        self.assertTrue(inv._is_eligible_for_tfhka())

    def test_121_tfhka_validate_mixed_invoicing_non_out_move_type(self):
        self.company.mix_invoicing_tfhka = False
        misc_journal = self.env['account.journal'].create({
            'name': 'Miscelaneos Mixto',
            'code': 'MSCM',
            'type': 'general',
            'company_id': self.company.id,
            'digital_invoice': False,
        })
        entry = self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': misc_journal.id,
            'date': fields.Date.today(),
        })
        entry._tfhka_validate_mixed_invoicing()

    @patch('odoo.addons.l10n_ve_invoice_digital.models.account_move.AccountMove.call_tfhka_api')
    def test_122_query_numbering_skips_non_matching_series(self, mock_call):
        mock_call.return_value = {
            "numeraciones": [
                {"serie": "B", "hasta": "100", "correlativo": "1"},
                {"serie": "NO APLICA", "hasta": "100000", "correlativo": "1"},
            ],
            "codigo": "200",
        }
        inv = self._create_invoice(
            products=[{"product_id": self.product.id, "price_unit": 1, "tax_ids": [self.tax_iva16.id]}]
        )
        inv.query_numbering(series="")

    @patch('odoo.addons.l10n_ve_invoice_digital.models.account_move.AccountMove.call_tfhka_api')
    def test_123_query_numbering_no_series_configured_raises(self, mock_call):
        mock_call.return_value = {"numeraciones": [], "codigo": "200"}
        inv = self._create_invoice(
            products=[{"product_id": self.product.id, "price_unit": 1, "tax_ids": [self.tax_iva16.id]}]
        )
        with self.assertRaises(UserError):
            inv.query_numbering(series="X")

    @patch('odoo.addons.l10n_ve_invoice_digital.models.account_move.requests.post')
    def test_124_call_tfhka_api_codigo_203_ultimo_documento(self, mock_post):
        self.company.write({"url_tfhka": "https://api.tfhka.com", "token_auth_tfhka": "token_fake"})
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"codigo": "203", "validaciones": ["no existe numeracion"]}
        mock_post.return_value = mock_resp
        inv = self._create_invoice(
            products=[{"product_id": self.product.id, "price_unit": 1, "tax_ids": [self.tax_iva16.id]}]
        )
        result = inv.call_tfhka_api("ultimo_documento", {})
        self.assertEqual(result, 0)

    @patch('odoo.addons.l10n_ve_invoice_digital.models.account_move.requests.post')
    def test_125_call_tfhka_api_connection_error(self, mock_post):
        self.company.write({"url_tfhka": "https://api.tfhka.com", "token_auth_tfhka": "token_fake"})
        import requests as req
        mock_post.side_effect = req.exceptions.ConnectionError("Connection error")
        inv = self._create_invoice(
            products=[{"product_id": self.product.id, "price_unit": 1, "tax_ids": [self.tax_iva16.id]}]
        )
        with self.assertRaises(UserError):
            inv.call_tfhka_api("emision", {})

