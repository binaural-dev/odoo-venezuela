from odoo.exceptions import UserError
from odoo import fields, Command
from odoo.tests import TransactionCase, tagged
from unittest.mock import patch, MagicMock

import logging

_logger = logging.getLogger(__name__)

@tagged('l10n_ve_invoice_digital', 'invoice digital') 
class TestStockPickingApiCalls(TransactionCase):

    def setUp(self):
        super(TestStockPickingApiCalls, self).setUp()

        # Monedas
        self.currency_vef = self.env.ref("base.VEF")
        self.currency_usd = self.env.ref("base.USD")

        # Crear modelos necesarios
        self.ProductProduct = self.env['product.product']
        self.ResPartner = self.env['res.partner']
        self.StockLocation = self.env['stock.location']
        self.StockPicking = self.env['stock.picking']
        self.StockQuant = self.env['stock.quant']
        self.StockWarehouse = self.env['stock.warehouse']
        self.UomUom = self.env['uom.uom']
        self.env.user.tz = 'America/Caracas'

        # Crear compañía (usamos la principal por defecto)
        self.company = self.env.ref("base.main_company")

        self.company.write(
            {
                "currency_id": self.currency_usd.id,
                "currency_foreign_id": self.currency_vef.id,
                "url_tfhka": "https://fake-api.com",
                "token_auth_tfhka": "fake-token",
                "group_sales_invoicing_series": True,
                "sequence_validation_tfhka": True,
                "invoice_digital_tfhka": True,
            }
        )
        
        # Crear unidad de medida (Unidades)
        self.uom_unit = self.env.ref('uom.product_uom_unit')
        
        # Crear categoría de producto
        self.product_category = self.env['product.category'].create({
            'name': 'Test Category',
        })
        
        # Crear producto consumible
        self.product_consumable = self.ProductProduct.create({
            'name': 'Producto Consumible',
            'type': 'consu',
            'categ_id': self.product_category.id,
            'uom_id': self.uom_unit.id,
            'uom_po_id': self.uom_unit.id,
        })
        
        # Crear producto almacenable
        self.product_storable = self.ProductProduct.create({
            'name': 'Producto Almacenable',
            'type': 'product',
            'categ_id': self.product_category.id,
            'uom_id': self.uom_unit.id,
            'uom_po_id': self.uom_unit.id,
        })
        
        # Crear partner (cliente)
        self.customer = self.env['res.partner'].create({
            'name': 'Cliente Prueba',
            'vat': 'V12345678',
            'prefix_vat': 'J',
            'country_id': self.env.ref('base.ve').id,
            'phone': '04141234567',
            'email': 'cliente@prueba.com',
            'street': 'Calle Falsa 123',
        })
        
        # Crear partner (proveedor)
        self.supplier = self.env['res.partner'].create({
            'name': 'Proveedor Prueba',
            'vat': 'J12345679',
            'prefix_vat': 'J',
            'country_id': self.env.ref('base.ve').id,
            'phone': '04141234567',
            'email': 'proveedor@prueba.com',
            'street': 'Calle Prueba 123',
        })
        
        # Obtener ubicaciones principales
        self.stock_location = self.env.ref('stock.stock_location_stock')
        self.customer_location = self.env.ref('stock.stock_location_customers')
        self.supplier_location = self.env.ref('stock.stock_location_suppliers')
        
        # Obtener tipos de operación
        self.picking_type_in = self.env.ref('stock.picking_type_in')
        self.picking_type_out = self.env.ref('stock.picking_type_out')
        self.picking_type_int = self.env.ref('stock.picking_type_internal')
        
        # Crear almacén adicional para pruebas
        self.warehouse_2 = self.StockWarehouse.create({
            'name': 'Almacén Secundario',
            'code': 'WH2',
        })
        
        # Crear ubicación adicional
        self.additional_location = self.StockLocation.create({
            'name': 'Ubicación Especial',
            'location_id': self.stock_location.id,
        })
        
        self.sequence_guide = self.env['ir.sequence'].search([('code', '=', 'guide.number')], limit=1)

        self.sequence_guide.write({'number_next_actual': 2,})

        # Crear stock inicial para producto almacenable
        self.StockQuant.create({
            'product_id': self.product_storable.id,
            'location_id': self.stock_location.id,
            'quantity': 100.0,
        })
    
    def create_picking(self, type=None, location=None, location_dest=None):
        type = type if type is not None else self.picking_type_int.id
        location = location if location is not None else self.stock_location.id
        location_dest = location_dest if location_dest is not None else self.customer_location.id

        return self.StockPicking.create({
            'location_id': location,
            'location_dest_id': location_dest,
            'partner_id': self.customer.id,
            'picking_type_id': type,
            'is_dispatch_guide': True,
            'move_ids': [(0, 0, {
                'name': self.product_storable.name,
                'product_id': self.product_storable.id,
                'product_uom_qty': 10,
                'product_uom': self.uom_unit.id,
                'location_id': self.stock_location.id,
                'location_dest_id': self.customer_location.id,
            })]
        })

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

    # Simula las respuestas SUCCES de la API de TFHKA
    def mock_api(endpoint_key, payload):
        if endpoint_key == "emision":
            return {"codigo": "200", "resultado": {"numeroControl": "00-00000001"}}
        elif endpoint_key == "ultimo_documento":
            return {"codigo": "200", "numeroDocumento": 1}
        elif endpoint_key == "consulta_numeraciones":
            return {"codigo": "200", "numeraciones": [{"serie": "NO APLICA", "hasta": "100000", "correlativo": "01"}]}
        return {"codigo": "200"}
    
    # API de TFHKA para consultar numeraciones
    @patch('odoo.addons.l10n_ve_invoice_digital.models.stock_picking.StockPicking.call_tfhka_api')
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
        
        outgoing_int_picking = self.create_picking()
        response = outgoing_int_picking.query_numbering()
        self.assertEqual(response, None)
        _logger.info("Test passed: Query numbering successfully.")

    # API de TFHKA para obtener el último número de documento
    @patch('odoo.addons.l10n_ve_invoice_digital.models.stock_picking.StockPicking.call_tfhka_api')
    def test_02_get_last_document_number_success(self, mock_call):
        mock_call.return_value = {
            "numeroDocumento": 126,
            "codigo": "200",
            "mensaje": "Consulta realizada exitosamente"
        }

        document_type = "04"
        outgoing_int_picking = self.create_picking()
        response = outgoing_int_picking.get_last_document_number(document_type)
        self.assertEqual(response, 126)
        _logger.info("Test passed: Get last document number successfully.")

    # API de TFHKA para generar documento digital (Guia de despacho)
    @patch('odoo.addons.l10n_ve_invoice_digital.models.stock_picking.StockPicking.call_tfhka_api')
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

        document_type = "04"
        document_number = "12345678"
        outgoing_int_picking = self.create_picking()
        response = outgoing_int_picking.generate_document_data(document_number, document_type)
        self.assertEqual(outgoing_int_picking.is_digitalized, True)
        _logger.info("Test passed: Document data generated successfully.")

    # Generar Guia de despacho interno
    @patch('odoo.addons.l10n_ve_invoice_digital.models.stock_picking.StockPicking.call_tfhka_api', side_effect=mock_api)
    def test_04_create_stock_picking(self, mock_call):
        """Test creating a stock picking with valid data."""
        outgoing_int_picking = self.create_picking()
        outgoing_int_picking.button_validate()

        self.assertEqual(outgoing_int_picking.is_digitalized, True)
        _logger.info("Test passed: Document digital generated successfully.")

    # Generar Guia de despacho entrega
    @patch('odoo.addons.l10n_ve_invoice_digital.models.stock_picking.StockPicking.call_tfhka_api', side_effect=mock_api)
    def test_05_create_stock_picking(self, mock_call):
        """Test creating a stock picking with valid data."""
        outgoing_out_picking = self.create_picking()
        outgoing_out_picking.button_validate()

        self.assertEqual(outgoing_out_picking.is_digitalized, True)
        _logger.info("Test passed: Document digital generated successfully.")
    
    # Generar Guia de despacho recepción
    @patch('odoo.addons.l10n_ve_invoice_digital.models.stock_picking.StockPicking.call_tfhka_api', side_effect=mock_api)
    def test_06_create_stock_picking(self, mock_call):
        """Test creating a stock picking with valid data."""
        incoming_picking = self.create_picking(self.picking_type_in.id, self.supplier_location.id, self.stock_location.id,)
        incoming_picking.button_validate()

        self.assertEqual(incoming_picking.is_digitalized, False)
        _logger.info("Test passed: Document digital generated successfully.")

    # Validacion de secuencia entre la API y Odoo
    @patch('odoo.addons.l10n_ve_invoice_digital.models.stock_picking.StockPicking.call_tfhka_api', side_effect=mock_api)
    def test_07_generate_document_digital_sequence_error(self, mock_call):
        """Test creating a stock picking with valid data."""
        self.sequence_guide.write({'number_next_actual': 1,})
        outgoing_out_picking = self.create_picking()

        with self.assertRaises(UserError):
            outgoing_out_picking.button_validate()

        _logger.info("Test passed: Sequence validation error raised as expected.")

    # Llamada a la API de TFHKA URL vacía
    def test_08_call_tfhka_api_URL_error(self):
        self.company.write({"url_tfhka": ""})

        outgoing_out_picking = self.create_picking()

        endpoint_key = "emision"
        payload={
            "serie": "",
            "tipoDocumento": "",
            "prefix": ""
        }
        with self.assertRaises(UserError):
            outgoing_out_picking.call_tfhka_api(endpoint_key, payload)

        _logger.info("Test passed: URL for TFHKA is empty, UserError raised as expected.")

    # Llamada a la API de TFHKA Token vacío
    def test_09_call_tfhka_api_token_error(self):
        self.company.write({"token_auth_tfhka": ""})

        outgoing_out_picking = self.create_picking()

        endpoint_key = "emision"
        payload={
            "serie": "",
            "tipoDocumento": "",
            "prefix": ""
        }
        with self.assertRaises(UserError):
            outgoing_out_picking.call_tfhka_api(endpoint_key, payload)

        _logger.info("Test passed: Token for TFHKA is empty, UserError raised as expected.")

    # Llamada a la API de TFHKA con error 400
    @patch('requests.post')
    def test_10_call_tfhka_api_status_code_400_error(self, mock_call):
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_call.return_value = mock_response

        outgoing_out_picking = self.create_picking()

        endpoint_key = "emision"
        payload={
            "serie": "",
            "tipoDocumento": "",
            "prefix": ""
        }
        with self.assertRaises(UserError):
            outgoing_out_picking.call_tfhka_api(endpoint_key, payload)

        _logger.info("Test passed: Token for TFHKA is empty, UserError raised as expected.")

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

        outgoing_out_picking = self.create_picking()

        endpoint_key = "emision"
        payload={
            "serie": "",
            "tipoDocumento": "",
            "prefix": ""
        }
        with self.assertRaises(UserError):
            outgoing_out_picking.call_tfhka_api(endpoint_key, payload)

        _logger.info("Test passed: Token for TFHKA is empty, UserError raised as expected.")

    # # Generar Guia de despacho con Sucursal
    # @patch('odoo.addons.l10n_ve_invoice_digital.models.stock_picking.StockPicking.call_tfhka_api', side_effect=mock_api)
    # def test_12_create_stock_picking_subsidiary(self, mock_call):
    #     self.company.write({"subsidiary": True})
    #     """Test creating a stock picking with valid data."""
    #     outgoing_out_picking = self.create_picking()
    #     subsidiary = self._create_subsidiary()
    #     outgoing_out_picking.subsidiary_origin_id = subsidiary.id

    #     outgoing_out_picking.button_validate()

    #     self.assertEqual(outgoing_out_picking.is_digitalized, True)
    #     _logger.info("Test passed: Document digital generated successfully.")
    
    # # Error de referencia de Retencion con Sucursal
    # @patch('odoo.addons.l10n_ve_invoice_digital.models.stock_picking.StockPicking.call_tfhka_api', side_effect=mock_api)
    # def test_13_create_stock_picking_subsidiary_error(self, mock_call):
    #     self.company.write({"subsidiary": True})
    #     outgoing_out_picking = self.create_picking()
    #     subsidiary = self._create_subsidiary()
    #     subsidiary.code = ""
    #     outgoing_out_picking.subsidiary_origin_id = subsidiary.id

    #     with self.assertRaises(UserError) as e:
    #         outgoing_out_picking.button_validate()
    #         _logger.error(e.exception)
    #     _logger.info("Test passed: The reference is empty, a user error was generated as expected.")
