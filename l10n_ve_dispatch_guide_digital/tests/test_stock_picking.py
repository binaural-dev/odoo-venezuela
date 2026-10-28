import logging

from odoo import Command, fields
from odoo.exceptions import UserError
from odoo.tests import Form, TransactionCase, tagged
from unittest.mock import patch

_logger = logging.getLogger(__name__)


# Simula las respuestas SUCCESS de la API de TFHKA (mismo formato usado por
# l10n_ve_invoice_digital/tests/test_account_move.py, ya que 'tfhka.api.client'
# es el mismo servicio compartido por ambos módulos).
def mock_api(company, endpoint_key, payload, *args, **kwargs):
    if endpoint_key == "emision":
        return {"codigo": "200", "resultado": {"numeroControl": "00-00000001"}}
    elif endpoint_key == "ultimo_documento":
        return {"codigo": "200", "numeroDocumento": 1}
    elif endpoint_key == "consulta_numeraciones":
        return {
            "numeraciones": [
                {"serie": "NO APLICA", "hasta": "100000", "correlativo": "01"},
            ],
            "codigo": "200",
            "mensaje": "Consulta realizada exitosamente",
        }


TFHKA_REQUEST_PATCH = "odoo.addons.l10n_ve_invoice_digital.services.tfhka_client.TfhkaApiClient._request"
GENERATE_DIGITAL_PATCH = "odoo.addons.l10n_ve_dispatch_guide_digital.models.stock_picking.StockPicking.generate_document_digital"


@tagged("post_install", "-at_install", "l10n_ve_dispatch_guide_digital")
class TestStockPickingApiCalls(TransactionCase):

    def setUp(self):
        super().setUp()
        self.env.user.tz = "America/Caracas"

        self.DispatchGuideService = self.env["tfhka.dispatch.guide.service"]
        self.StockPicking = self.env["stock.picking"]
        self.StockQuant = self.env["stock.quant"]

        # ───────────────────────────────────────────────────── monedas / compañía
        self.currency_vef = self.env.ref("base.VEF")
        self.currency_usd = self.env.ref("base.USD")
        self.company = self.env.ref("base.main_company")

        self.company.write(
            {
                "url_tfhka": "https://fake-api.com",
                "token_auth_tfhka": "fake-token",
                "invoice_digital_tfhka": True,
                "dispatch_guide_digital_tfhka": True,
                "country_id": self.env.ref("base.ve").id,
                # Las pruebas que exigen datos de transporte lo activan
                # explícitamente; no depender de la configuración de la base.
                "transport_data_required": False,
            }
        )

        # ───────────────────────────────────────────────────── ubicaciones / tipos
        self.stock_location = self.env.ref("stock.stock_location_stock")
        self.customer_location = self.env.ref("stock.stock_location_customers")

        self.picking_type_in = self.env.ref("stock.picking_type_in")
        self.picking_type_int = self.env.ref("stock.picking_type_internal")

        self.uom_unit = self.env.ref("uom.product_uom_unit")

        # ───────────────────────────────────────────────────── partners
        self.customer = self.env["res.partner"].create(
            {
                "name": "Cliente Prueba",
                "vat": "V12345678",
                "prefix_vat": "V",
                "country_id": self.env.ref("base.ve").id,
                "phone": "04141234567",
                "email": "cliente@prueba.com",
                "street": "Calle Falsa 123",
            }
        )

        self.customer_child = self.env["res.partner"].create(
            {
                "name": "Contacto Entrega",
                "parent_id": self.customer.id,
                "type": "delivery",
            }
        )

        self.customer_bare = self.env["res.partner"].create(
            {
                "name": "Sin Dirección",
                "country_id": False,
            }
        )

        # ───────────────────────────────────────────────────── impuestos
        self.tax_group = self.env["account.tax.group"].create({"name": "IVA"})
        self.tax_iva16 = self.env["account.tax"].create(
            {
                "name": "IVA 16%",
                "amount": 16,
                "amount_type": "percent",
                "type_tax_use": "sale",
                "tax_group_id": self.tax_group.id,
            }
        )

        # ───────────────────────────────────────────────────── condiciones de pago
        self.payment_term_credit = self.env["account.payment.term"].create(
            {
                "name": "30 dias",
                "line_ids": [
                    Command.create({"nb_days": 30, "value": "percent", "value_amount": 100})
                ],
            }
        )
        self.payment_term_immediate = self.env["account.payment.term"].create(
            {
                "name": "Inmediato",
                "line_ids": [
                    Command.create({"nb_days": 0, "value": "percent", "value_amount": 100})
                ],
            }
        )

        # ───────────────────────────────────────────────────── motivos de traslado
        self.transfer_reason_sale = self.env.ref("l10n_ve_stock_account.transfer_reason_sale")
        self.transfer_reason_other_causes = self.env.ref(
            "l10n_ve_stock_account.transfer_reason_other_causes"
        )

        # ───────────────────────────────────────────────────── productos
        self.product_category = self.env["product.category"].create({"name": "Test Category"})

        self.product_storable = self.env["product.product"].create(
            {
                "name": "Producto Almacenable",
                # O19: type es consu|service|combo; lo almacenable es is_storable.
                "type": "consu",
                "is_storable": True,
                "categ_id": self.product_category.id,
                "uom_id": self.uom_unit.id,
                "barcode": "1111111111",
                "taxes_id": [Command.set([self.tax_iva16.id])],
            }
        )

        self.product_service = self.env["product.product"].create(
            {
                "name": "Servicio de Prueba",
                "type": "service",
                "categ_id": self.product_category.id,
            }
        )

        self.product_national = self.env["product.product"].create(
            {
                "name": "Producto Nacional",
                # O19: type es consu|service|combo; lo almacenable es is_storable.
                "type": "consu",
                "is_storable": True,
                "categ_id": self.product_category.id,
                "uom_id": self.uom_unit.id,
                "country_of_origin": self.env.ref("base.ve").id,
                "taxes_id": [Command.set([self.tax_iva16.id])],
            }
        )

        self.product_imported = self.env["product.product"].create(
            {
                "name": "Producto Importado",
                # O19: type es consu|service|combo; lo almacenable es is_storable.
                "type": "consu",
                "is_storable": True,
                "categ_id": self.product_category.id,
                "uom_id": self.uom_unit.id,
                "country_of_origin": self.env.ref("base.us").id,
                "taxes_id": [Command.set([self.tax_iva16.id])],
            }
        )

        for product in (
            self.product_storable,
            self.product_national,
            self.product_imported,
        ):
            self.StockQuant.create(
                {
                    "product_id": product.id,
                    "location_id": self.stock_location.id,
                    "quantity": 100.0,
                }
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def create_picking(self, picking_type=None, products=None, partner=None):
        """Picking manual (sin sale_id), como una transferencia interna directa."""
        picking_type = picking_type if picking_type is not None else self.picking_type_int
        products = products if products is not None else [(self.product_storable, 10)]

        location = picking_type.default_location_src_id.id or self.stock_location.id
        location_dest = picking_type.default_location_dest_id.id or self.customer_location.id

        vals = {
            "location_id": location,
            "location_dest_id": location_dest,
            "picking_type_id": picking_type.id,
            "is_dispatch_guide": True,
        }
        if partner is not False:
            vals["partner_id"] = (partner or self.customer).id

        vals["move_ids"] = [
            Command.create(
                {
                    # O19: stock.move.name ya no existe (description_picking).
                    "product_id": product.id,
                    "product_uom_qty": qty,
                    "product_uom": product.uom_id.id,
                    "location_id": location,
                    "location_dest_id": location_dest,
                }
            )
            for product, qty in products
        ]

        return self.StockPicking.create(vals)

    def validate_picking(self, picking):
        for move in picking.move_ids:
            move.quantity = move.product_uom_qty
        return picking.button_validate()

    def create_sale_dispatch_guide(
        self,
        order_lines,
        currency=None,
        foreign_rate=10.0,
        partner=None,
        payment_term=None,
    ):
        """Crea una orden de venta (documento='dispatch_guide'), la confirma y
        deja el picking resultante listo para validar, con transfer_reason_id
        'sale' ya asignado.
        """
        currency = currency or self.currency_vef
        order_vals = {
            "partner_id": (partner or self.customer).id,
            "document": "dispatch_guide",
            "currency_id": currency.id,
            "manually_set_rate": True,
            "foreign_rate": foreign_rate,
            "foreign_inverse_rate": 1 / foreign_rate,
        }
        if payment_term:
            order_vals["payment_term_id"] = payment_term.id

        order = self.env["sale.order"].create(order_vals)

        created_lines = []
        for line_vals in order_lines:
            vals = {
                "order_id": order.id,
                "currency_id": currency.id,
                "foreign_currency_id": self.currency_usd.id
                if currency == self.currency_vef
                else self.currency_vef.id,
                "foreign_rate": foreign_rate,
                "display_type": False,
            }
            vals.update(line_vals)
            created_lines.append(
                (self.env["sale.order.line"].create(vals), line_vals.get("price_unit"))
            )

        # currency_id es un campo computado (a partir de la lista de precios); lo
        # forzamos explícitamente para controlar la rama VEF/extranjera en las
        # pruebas, sin depender de qué lista de precios resuelva el partner.
        order.currency_id = currency.id
        order.action_confirm()
        order.currency_id = currency.id

        # price_unit tambien es computado desde la tarifa/producto y en O19 el
        # compute pisa el valor pasado en el create (el producto de prueba no
        # define list_price, asi que cae a 1.0). Se reimpone tras confirmar,
        # igual que con currency_id.
        for line, price_unit in created_lines:
            if price_unit is not None:
                line.price_unit = price_unit
        picking = order.picking_ids
        picking.transfer_reason_id = self.transfer_reason_sale.id
        return order, picking

    # ==================================================================
    # send_document
    # ==================================================================

    @patch(TFHKA_REQUEST_PATCH, side_effect=mock_api)
    def test_send_document_success(self, mock_call):
        sequence = self.env["ir.sequence"].search(
            [("code", "=", "guide.number"), ("company_id", "=", self.company.id)]
        )
        sequence.write({"number_next_actual": 2})

        picking = self.create_picking()
        self.validate_picking(picking)

        # button_validate() only enqueues now (see tfhka.digitalization.mixin);
        # the cron is what actually calls TFHKA.
        self.assertEqual(picking.tfhka_digitalization_state, "queued")
        self.env["stock.picking"]._tfhka_cron_process_queue()

        self.assertTrue(picking.is_digitalized)
        self.assertEqual(picking.control_number_tfhka, "00-00000001")
        self.assertTrue(picking.guide_number)

        messages = picking.message_ids.filtered(lambda m: "successfully digitized" in (m.body or ""))
        self.assertTrue(messages, "Debe publicarse un mensaje de digitalización exitosa.")

    def test_send_document_already_digitalized_raises(self):
        picking = self.create_picking()
        picking.is_digitalized = True

        with self.assertRaises(UserError):
            self.DispatchGuideService.send_document(picking)

    @patch(TFHKA_REQUEST_PATCH, side_effect=mock_api)
    def test_send_document_sequence_mismatch_raises(self, mock_call):
        # La validación de secuencia ya no es configurable: siempre está
        # activa (ver eliminación de sequence_validation_tfhka).
        sequence = self.env["ir.sequence"].search(
            [("code", "=", "guide.number"), ("company_id", "=", self.company.id)]
        )
        sequence.write({"number_next_actual": 99})

        picking = self.create_picking()
        self.validate_picking(picking)

        # The mismatch now only surfaces once the cron actually attempts the
        # digitalization -- button_validate() itself never calls TFHKA, so it
        # can't raise synchronously anymore. The queue halts with the
        # document left in 'error' instead.
        self.env["stock.picking"]._tfhka_cron_process_queue()
        self.assertEqual(picking.tfhka_digitalization_state, "error")
        self.assertIn("does not match the sequence", picking.tfhka_digitalization_error)

    # ==================================================================
    # generate_document_data / _register_success (flujo completo)
    # ==================================================================

    @patch(TFHKA_REQUEST_PATCH, side_effect=mock_api)
    def test_generate_document_data_full_flow_sale_vef_with_tax(self, mock_call):
        sequence = self.env["ir.sequence"].search(
            [("code", "=", "guide.number"), ("company_id", "=", self.company.id)]
        )
        sequence.write({"number_next_actual": 2})

        order, picking = self.create_sale_dispatch_guide(
            order_lines=[
                {
                    "product_id": self.product_storable.id,
                    "product_uom_qty": 2,
                    "price_unit": 100,
                    "tax_ids": [Command.set([self.tax_iva16.id])],
                    "name": "Línea con impuesto",
                }
            ],
            currency=self.currency_vef,
            payment_term=self.payment_term_credit,
        )

        self.validate_picking(picking)
        self.env["stock.picking"]._tfhka_cron_process_queue()

        self.assertTrue(picking.is_digitalized)
        self.assertEqual(picking.control_number_tfhka, "00-00000001")
        self.assertTrue(picking.guide_number)

    @patch(TFHKA_REQUEST_PATCH, side_effect=mock_api)
    def test_generate_document_data_without_partner_skips_additional_info(self, mock_call):
        picking = self.create_picking(partner=False)
        self.DispatchGuideService.generate_document_data(picking, "5", "04")
        self.assertTrue(picking.is_digitalized)

    @patch(TFHKA_REQUEST_PATCH)
    def test_generate_document_data_empty_response_skips_register_success(self, mock_call):
        mock_call.return_value = None
        picking = self.create_picking()
        self.DispatchGuideService.generate_document_data(picking, "5", "04")
        self.assertFalse(picking.is_digitalized)

    # ==================================================================
    # _prepare_identification
    # ==================================================================

    def test_prepare_identification_without_date_deadline(self):
        picking = self.create_picking()
        ident = self.DispatchGuideService._prepare_identification(picking, "04", "1")
        self.assertEqual(ident["fechaVencimiento"], ident["fechaEmision"])

    def test_prepare_identification_with_date_deadline(self):
        picking = self.create_picking()
        picking.date_deadline = fields.Datetime.from_string("2026-09-01 10:00:00")
        ident = self.DispatchGuideService._prepare_identification(picking, "04", "1")
        self.assertEqual(ident["fechaVencimiento"], "01/09/2026")

    def test_prepare_identification_empty_recordset(self):
        empty_picking = self.StockPicking.browse()
        result = self.DispatchGuideService._prepare_identification(empty_picking, "04", "1")
        self.assertIsNone(result)

    # ==================================================================
    # _get_payment_type
    # ==================================================================

    def test_get_payment_type_without_sale_id(self):
        picking = self.create_picking()
        self.assertIsNone(self.DispatchGuideService._get_payment_type(picking))

    def test_get_payment_type_credit(self):
        order, picking = self.create_sale_dispatch_guide(
            order_lines=[
                {
                    "product_id": self.product_storable.id,
                    "product_uom_qty": 1,
                    "price_unit": 10,
                    "tax_ids": [Command.set([self.tax_iva16.id])],
                    "name": "Línea",
                }
            ],
            payment_term=self.payment_term_credit,
        )
        self.assertEqual(self.DispatchGuideService._get_payment_type(picking), "Crédito")

    def test_get_payment_type_immediate(self):
        order, picking = self.create_sale_dispatch_guide(
            order_lines=[
                {
                    "product_id": self.product_storable.id,
                    "product_uom_qty": 1,
                    "price_unit": 10,
                    "tax_ids": [Command.set([self.tax_iva16.id])],
                    "name": "Línea",
                }
            ],
            payment_term=self.payment_term_immediate,
        )
        self.assertEqual(self.DispatchGuideService._get_payment_type(picking), "Inmediato")

    # ==================================================================
    # _prepare_detail_lines
    # ==================================================================

    def test_prepare_detail_lines_generic_without_sale(self):
        picking = self.create_picking(
            products=[(self.product_storable, 5), (self.product_service, 2)]
        )
        items = self.DispatchGuideService._prepare_detail_lines(picking)

        self.assertEqual(len(items), 2)
        for item in items:
            self.assertEqual(item["precioUnitario"], "0")
            self.assertEqual(item["valorTotalItem"], "0")

        indicators = {item["indicadorBienoServicio"] for item in items}
        self.assertEqual(indicators, {"1", "2"})

    @patch(TFHKA_REQUEST_PATCH, side_effect=mock_api)
    def test_prepare_detail_lines_sale_with_tax_vef(self, mock_call):
        order, picking = self.create_sale_dispatch_guide(
            order_lines=[
                {
                    "product_id": self.product_storable.id,
                    "product_uom_qty": 3,
                    "price_unit": 50,
                    "tax_ids": [Command.set([self.tax_iva16.id])],
                    "name": "Línea con impuesto",
                }
            ],
            currency=self.currency_vef,
        )
        self.validate_picking(picking)

        items = self.DispatchGuideService._prepare_detail_lines(picking)
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item["codigoImpuesto"], "G")
        self.assertEqual(item["tasaIVA"], "16.0")
        self.assertEqual(item["precioUnitario"], "50.0")

    @patch(TFHKA_REQUEST_PATCH, side_effect=mock_api)
    def test_prepare_detail_lines_sale_without_tax_foreign_currency(self, mock_call):
        order, picking = self.create_sale_dispatch_guide(
            order_lines=[
                {
                    "product_id": self.product_storable.id,
                    "product_uom_qty": 2,
                    "price_unit": 100,
                    "tax_ids": [Command.clear()],
                    "name": "Línea sin impuesto",
                }
            ],
            currency=self.currency_usd,
            foreign_rate=10.0,
        )
        self.validate_picking(picking)

        sale_line = order.order_line.filtered(lambda l: l.product_id)
        expected_unit_price = round(sale_line.foreign_price, 2)

        items = self.DispatchGuideService._prepare_detail_lines(picking)
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item["codigoImpuesto"], "E")
        self.assertEqual(item["tasaIVA"], "0.0")
        self.assertEqual(item["precioUnitario"], str(expected_unit_price))

    # ==================================================================
    # _prepare_dispatch_guide
    # ==================================================================

    def test_prepare_dispatch_guide_origin_nacional(self):
        order, picking = self.create_sale_dispatch_guide(
            order_lines=[
                {
                    "product_id": self.product_national.id,
                    "product_uom_qty": 1,
                    "price_unit": 10,
                    "name": "Nacional",
                }
            ],
        )
        guide = self.DispatchGuideService._prepare_dispatch_guide(picking)
        self.assertEqual(guide["origenProducto"], "Nacional")

    def test_prepare_dispatch_guide_origin_importado(self):
        order, picking = self.create_sale_dispatch_guide(
            order_lines=[
                {
                    "product_id": self.product_imported.id,
                    "product_uom_qty": 1,
                    "price_unit": 10,
                    "name": "Importado",
                }
            ],
        )
        guide = self.DispatchGuideService._prepare_dispatch_guide(picking)
        self.assertEqual(guide["origenProducto"], "Importado")

    def test_prepare_dispatch_guide_origin_mixed(self):
        order, picking = self.create_sale_dispatch_guide(
            order_lines=[
                {
                    "product_id": self.product_national.id,
                    "product_uom_qty": 1,
                    "price_unit": 10,
                    "name": "Nacional",
                },
                {
                    "product_id": self.product_imported.id,
                    "product_uom_qty": 1,
                    "price_unit": 10,
                    "name": "Importado",
                },
            ],
        )
        guide = self.DispatchGuideService._prepare_dispatch_guide(picking)
        self.assertEqual(guide["origenProducto"], "Nacional e Importado")

    def test_prepare_dispatch_guide_origin_sin_definir(self):
        picking = self.create_picking()
        guide = self.DispatchGuideService._prepare_dispatch_guide(picking)
        self.assertEqual(guide["origenProducto"], "Sin origen definido")

    def test_prepare_dispatch_guide_empty_recordset(self):
        empty_picking = self.StockPicking.browse()
        result = self.DispatchGuideService._prepare_dispatch_guide(empty_picking)
        self.assertIsNone(result)

    def test_prepare_dispatch_guide_other_causes_reason(self):
        picking = self.create_picking()
        picking.transfer_reason_id = self.transfer_reason_other_causes.id
        picking.other_causes_transfer_reason = "Reparación de emergencia"

        guide = self.DispatchGuideService._prepare_dispatch_guide(picking)
        self.assertEqual(guide["motivoTraslado"], "Reparación de emergencia")

    def test_prepare_dispatch_guide_other_transfer_reason(self):
        picking = self.create_picking()
        picking.transfer_reason_id = self.transfer_reason_sale.id

        guide = self.DispatchGuideService._prepare_dispatch_guide(picking)
        self.assertEqual(guide["motivoTraslado"], self.transfer_reason_sale.name)

    @patch(TFHKA_REQUEST_PATCH, side_effect=mock_api)
    def test_prepare_dispatch_guide_with_shipping_weight(self, mock_call):
        self.product_storable.weight = 5.0
        picking = self.create_picking(products=[(self.product_storable, 10)])
        self.validate_picking(picking)

        guide = self.DispatchGuideService._prepare_dispatch_guide(picking)
        expected = f"{picking.shipping_weight:.2f} {picking.weight_uom_name}"
        self.assertEqual(guide["pesoOVolumenTotal"], expected)
        self.assertNotEqual(guide["pesoOVolumenTotal"], "Sin peso")

    def test_prepare_dispatch_guide_without_shipping_weight(self):
        picking = self.create_picking()
        guide = self.DispatchGuideService._prepare_dispatch_guide(picking)
        self.assertEqual(guide["pesoOVolumenTotal"], "Sin peso")

    def test_prepare_dispatch_guide_with_note(self):
        picking = self.create_picking()
        picking.note = "<p>Entrega urgente</p>"
        guide = self.DispatchGuideService._prepare_dispatch_guide(picking)
        self.assertEqual(guide["descripcionServicio"], "Entrega urgente")

    def test_prepare_dispatch_guide_without_note(self):
        picking = self.create_picking()
        guide = self.DispatchGuideService._prepare_dispatch_guide(picking)
        self.assertEqual(guide["descripcionServicio"], "Sin descripción")

    # ==================================================================
    # _prepare_additional_information
    # ==================================================================

    def test_prepare_additional_information_with_partner(self):
        picking = self.create_picking()
        info = self.DispatchGuideService._prepare_additional_information(picking)
        self.assertEqual(len(info), 1)
        self.assertEqual(info[0]["campo"], "direccionEntrega")

    def test_prepare_additional_information_without_partner(self):
        picking = self.create_picking(partner=False)
        info = self.DispatchGuideService._prepare_additional_information(picking)
        self.assertEqual(info, [])

    # ==================================================================
    # _get_party_source / _get_party_address
    # ==================================================================

    def test_get_party_source_with_parent(self):
        picking = self.create_picking(partner=self.customer_child)
        party = self.DispatchGuideService._get_party_source(picking)
        self.assertEqual(party, self.customer)

    def test_get_party_source_without_parent(self):
        picking = self.create_picking(partner=self.customer)
        party = self.DispatchGuideService._get_party_source(picking)
        self.assertEqual(party, self.customer)

    def test_get_party_address_defined(self):
        address = self.DispatchGuideService._get_party_address(self.customer)
        self.assertTrue(address)
        self.assertNotEqual(address, "no definida")

    def test_get_party_address_not_defined(self):
        address = self.DispatchGuideService._get_party_address(self.customer_bare)
        self.assertEqual(address, "no definida")

    # ==================================================================
    # stock_picking.py — button_validate
    # ==================================================================

    @patch(GENERATE_DIGITAL_PATCH)
    def test_button_validate_triggers_digitalization(self, mock_generate):
        self.company.dispatch_guide_digital_tfhka = True
        picking = self.create_picking(picking_type=self.picking_type_int)
        self.validate_picking(picking)
        # button_validate() only enqueues now (see tfhka.digitalization.mixin);
        # generate_document_digital() is only called later by the cron.
        mock_generate.assert_not_called()
        self.assertEqual(picking.tfhka_digitalization_state, "queued")

    @patch(GENERATE_DIGITAL_PATCH)
    def test_button_validate_skipped_when_company_flag_disabled(self, mock_generate):
        self.company.dispatch_guide_digital_tfhka = False
        picking = self.create_picking(picking_type=self.picking_type_int)
        self.validate_picking(picking)
        mock_generate.assert_not_called()

    @patch(GENERATE_DIGITAL_PATCH)
    def test_button_validate_skipped_when_already_digitalized(self, mock_generate):
        self.company.dispatch_guide_digital_tfhka = True
        picking = self.create_picking(picking_type=self.picking_type_int)
        picking.is_digitalized = True
        self.validate_picking(picking)
        mock_generate.assert_not_called()

    @patch(GENERATE_DIGITAL_PATCH)
    def test_button_validate_skipped_when_not_dispatch_guide(self, mock_generate):
        self.company.dispatch_guide_digital_tfhka = True
        picking = self.create_picking(picking_type=self.picking_type_int)
        picking.is_dispatch_guide = False
        self.validate_picking(picking)
        mock_generate.assert_not_called()

    @patch(GENERATE_DIGITAL_PATCH)
    def test_button_validate_skipped_when_incoming(self, mock_generate):
        self.company.dispatch_guide_digital_tfhka = True
        picking = self.create_picking(
            picking_type=self.picking_type_in,
            products=[(self.product_storable, 10)],
        )
        self.validate_picking(picking)
        mock_generate.assert_not_called()

    # ==================================================================
    # _compute_visibility_button
    # ==================================================================

    def test_compute_visibility_button_company_flag_enabled(self):
        self.company.dispatch_guide_digital_tfhka = True
        picking = self.create_picking()
        picking._compute_visibility_button()
        self.assertFalse(picking.show_digital_dispatch_guide)

    def test_compute_visibility_button_company_flag_disabled(self):
        self.company.dispatch_guide_digital_tfhka = False
        picking = self.create_picking()
        picking._compute_visibility_button()
        self.assertTrue(picking.show_digital_dispatch_guide)

    # ==================================================================
    # _set_guide_number
    # ==================================================================

    def test_set_guide_number_controls_disabled(self):
        picking = self.create_picking()
        # Picking en borrador: dispatch_guide_controls es False (state != done).
        picking._set_guide_number()
        self.assertFalse(picking.guide_number)

    def test_set_guide_number_company_flag_disabled_sets_number(self):
        self.company.dispatch_guide_digital_tfhka = False
        picking = self.create_picking()
        self.validate_picking(picking)
        self.assertTrue(picking.guide_number)

    def test_set_guide_number_digital_flag_enabled_and_digitalized(self):
        self.company.dispatch_guide_digital_tfhka = False
        picking = self.create_picking()
        self.validate_picking(picking)
        picking.guide_number = False

        self.company.dispatch_guide_digital_tfhka = True
        picking.is_digitalized = True
        picking._set_guide_number()
        self.assertTrue(picking.guide_number)

    def test_set_guide_number_digital_flag_enabled_not_digitalized(self):
        self.company.dispatch_guide_digital_tfhka = False
        picking = self.create_picking()
        self.validate_picking(picking)
        picking.guide_number = False

        self.company.dispatch_guide_digital_tfhka = True
        picking.is_digitalized = False
        picking._set_guide_number()
        self.assertFalse(picking.guide_number)


    # ==================================================================
    # Datos de transporte (conductor / vehículo)
    # ==================================================================

    def _set_transport_data(self, picking):
        picking.write({
            "transport_driver_name": "Pedro Pérez",
            "transport_driver_vat": "V-12.345.678",
            "transport_vehicle_brand": "Ford",
            "transport_vehicle_model": "Cargo 1721",
            "transport_vehicle_plate": "a12 bc3d",
            "transport_trailer_plate": "B45EF6G",
        })

    def test_prepare_dispatch_guide_includes_driver_and_vehicle(self):
        picking = self.create_picking()
        self._set_transport_data(picking)
        guide = self.DispatchGuideService._prepare_dispatch_guide(picking)
        self.assertEqual(guide["conductor"], {
            "nombreCompleto": "Pedro Pérez",
            "tipoIdentificacion": "V",
            "numeroIdentificacion": "12345678",
        })
        self.assertEqual(guide["vehiculo"], {"numeroPlaca": "A12BC3D"})

    def test_prepare_dispatch_guide_without_transport_data(self):
        picking = self.create_picking()
        guide = self.DispatchGuideService._prepare_dispatch_guide(picking)
        self.assertNotIn("conductor", guide)
        self.assertNotIn("vehiculo", guide)

    def test_prepare_transport_data_omits_empty_values(self):
        picking = self.create_picking()
        picking.transport_driver_name = "Pedro Pérez"
        transport = self.DispatchGuideService._prepare_transport_data(picking)
        self.assertEqual(transport, {"conductor": {"nombreCompleto": "Pedro Pérez"}})

    def test_prepare_additional_information_with_transport_data(self):
        picking = self.create_picking()
        self._set_transport_data(picking)
        info = self.DispatchGuideService._prepare_additional_information(picking)
        self.assertEqual([item["campo"] for item in info], [
            "direccionEntrega", "marcaVehiculo", "modeloVehiculo", "placaBatea",
        ])
        values = {item["campo"]: item["valor"] for item in info}
        self.assertEqual(values["marcaVehiculo"], "Ford")
        self.assertEqual(values["modeloVehiculo"], "Cargo 1721")
        self.assertEqual(values["placaBatea"], "B45EF6G")

    def test_delivery_address_uses_standard_address_fields(self):
        picking = self.create_picking()
        info = self.DispatchGuideService._prepare_additional_information(picking)
        self.assertIn("Calle Falsa 123", info[0]["valor"])

    def test_emitted_payload_includes_transport_data(self):
        payloads = []

        def capture_api(company, endpoint_key, payload, *args, **kwargs):
            if endpoint_key == "emision":
                payloads.append(payload)
            return mock_api(company, endpoint_key, payload, *args, **kwargs)

        picking = self.create_picking()
        self._set_transport_data(picking)
        with patch(TFHKA_REQUEST_PATCH, side_effect=capture_api):
            self.DispatchGuideService.generate_document_data(picking, "5", "04")

        self.assertTrue(picking.is_digitalized)
        document = payloads[0]["documentoElectronico"]
        self.assertEqual(document["guiaDespacho"]["conductor"]["nombreCompleto"], "Pedro Pérez")
        self.assertEqual(document["guiaDespacho"]["vehiculo"]["numeroPlaca"], "A12BC3D")
        fields_sent = [item["campo"] for item in document["infoAdicional"]]
        self.assertIn("placaBatea", fields_sent)

    def test_required_transport_data_blocks_validation_and_queue(self):
        self.company.transport_data_required = True
        picking = self.create_picking()
        with self.assertRaises(UserError):
            self.validate_picking(picking)
        self.assertNotEqual(picking.tfhka_digitalization_state, "queued")

    @patch(TFHKA_REQUEST_PATCH, side_effect=mock_api)
    def test_missing_transport_data_in_queue_is_data_error(self, mock_call):
        sequence = self.env["ir.sequence"].search(
            [("code", "=", "guide.number"), ("company_id", "=", self.company.id)]
        )
        sequence.write({"number_next_actual": 2})
        self.company.transport_data_required = False
        picking = self.create_picking()
        self.validate_picking(picking)
        self.assertEqual(picking.tfhka_digitalization_state, "queued")

        # La compañía activa la exigencia con la guía ya en cola.
        self.company.transport_data_required = True
        self.env["stock.picking"]._tfhka_cron_process_queue()

        self.assertFalse(picking.is_digitalized)
        self.assertEqual(picking.tfhka_digitalization_state, "data_error")
        self.assertIn("transport data", picking.tfhka_digitalization_error)

    def test_disabling_dispatch_guide_keeps_transport_requirement(self):
        # "Exigir datos de transporte" no depende de TFHKA: la empresa puede
        # exigirlos aunque la guía digital esté apagada.
        self.company.transport_data_required = True
        self.company.dispatch_guide_digital_tfhka = False
        self.assertTrue(self.company.transport_data_required)

    def test_prepare_transport_data_license_contact_type_number(self):
        picking = self.create_picking()
        picking.write({
            "transport_driver_name": "Pedro Pérez",
            "transport_driver_license_type": "5",
            "transport_driver_contact": "04141234567",
            "transport_vehicle_type": "Camión",
            "transport_vehicle_number": "U-07",
            "transport_vehicle_plate": "A12BC3D",
        })
        transport = self.DispatchGuideService._prepare_transport_data(picking)
        self.assertEqual(transport["conductor"]["tipoLicencia"], "5to grado")
        self.assertEqual(transport["conductor"]["infoContacto"], "04141234567")
        self.assertEqual(transport["vehiculo"], {
            "tipoVehiculo": "Camión",
            "numeroTransporte": "U-07",
            "numeroPlaca": "A12BC3D",
        })

    def test_transport_editable_when_digitalization_failed(self):
        picking = self.create_picking()
        self.validate_picking(picking)
        self.assertEqual(picking.state, "done")
        form = Form(picking)
        self.assertTrue(form._get_modifier("transport_vehicle_plate", "readonly"))
        picking.tfhka_digitalization_state = "data_error"
        form = Form(picking)
        self.assertFalse(form._get_modifier("transport_vehicle_plate", "readonly"))
        self.assertFalse(form._get_modifier("transport_driver_license_type", "readonly"))

