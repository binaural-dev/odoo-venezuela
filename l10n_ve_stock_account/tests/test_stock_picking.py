from odoo import _
from odoo.tests import Form
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError
from odoo.tests import tagged
import logging

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "l10n_ve_stock_account")
class TestStockPickingInvoice(TransactionCase):
    """Tests for generating invoices from sale orders in Venezuelan localization."""

    def setUp(self):
        super(TestStockPickingInvoice, self).setUp()
        self.currency_usd = self.env.ref("base.USD")
        self.currency_vef = self.env.ref("base.VEF")
        self.company = self.env.ref("base.main_company")
        self.company.write(
            {
                "currency_id": self.currency_vef.id,
                "currency_foreign_id": self.currency_usd.id,
            }
        )

        self.partner = self.env["res.partner"].create(
            {
                "name": "Cliente Prueba",
                "vat": "J12345678",
                "prefix_vat": "J",
                "country_id": self.env.ref("base.ve").id,
                "phone": "04141234567",
                "email": "cliente@prueba.com",
                "street": "Calle Falsa 123",
            }
        )

        self.tax_group = self.env["account.tax.group"].create(
            {
                "name": "IVA",
                "sequence": 10,
            }
        )

        # Crear impuesto IVA 16%
        self.tax_iva16 = self.env["account.tax"].create(
            {
                "name": "IVA 16%",
                "amount": 16,
                "amount_type": "percent",
                "type_tax_use": "sale",
                "tax_group_id": self.tax_group.id,
                "country_id": self.env.ref("base.ve").id,
            }
        )

        # Crear el producto
        self.product = self.env["product.product"].create(
            {
                "name": "Producto Prueba",
                "type": "product",
                "list_price": 100,
                "barcode": "123456789",
                "taxes_id": [(6, 0, [self.tax_iva16.id])],
                "detailed_type": "product",
            }
        )

        self.partner_a = self.env["res.partner"].create(
            {
                "name": "Test Partner A",
                "customer_rank": 1,
            }
        )

        sequence = self.env["ir.sequence"].create(
            {
                "name": "Secuencia Factura",
                "code": "account.move",
                "prefix": "INV/",
                "padding": 8,
                "number_next_actual": 2,
            }
        )
        refund_sequence = self.env["ir.sequence"].create(
            {
                "name": "nota de credito",
                "code": "",
                "prefix": "NC/",
                "padding": 8,
                "number_next_actual": 2,
            }
        )

        self.journal = self.env["account.journal"].create(
            {
                "name": "Diario de Ventas",
                "code": "VEN",
                "type": "sale",
                "sequence_id": sequence.id,
                "refund_sequence_id": refund_sequence.id,
                "company_id": self.env.company.id,
                "is_contingency": False,
            }
        )
        self.company.write(
            {
                "customer_journal_id": self.journal.id,
            }
        )

    def create_sale_order(self):
        rate = 5.0
        order = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "manually_set_rate": True,
                "foreign_rate": rate,
                "foreign_inverse_rate": 1 / rate,
                "document": "dispatch_guide",
            }
        )

        order_line_01 = self.env["sale.order.line"].create(
            {
                "product_id": self.product.id,
                "product_uom_qty": 2,
                "price_unit": 100,
                "tax_id": [(6, 0, [self.tax_iva16.id])],
                "order_id": order.id,
                "currency_id": self.currency_vef.id,
                "foreign_currency_id": self.currency_usd.id,
                "foreign_rate": rate,
                "display_type": False,
                "name": "Test Product Line",
            }
        )

        order_line_02 = self.env["sale.order.line"].create(
            {
                "product_id": False,
                "product_uom_qty": 0,
                "price_unit": 0,
                "tax_id": [(6, 0, [self.tax_iva16.id])],
                "order_id": order.id,
                "currency_id": self.currency_vef.id,
                "foreign_currency_id": self.currency_usd.id,
                "foreign_rate": 0,
                "display_type": "line_section",
                "name": "Section Line",
            }
        )

        order_line_03 = self.env["sale.order.line"].create(
            {
                "product_id": False,
                "product_uom_qty": 0,
                "price_unit": 0,
                "tax_id": [(6, 0, [self.tax_iva16.id])],
                "order_id": order.id,
                "currency_id": self.currency_vef.id,
                "foreign_currency_id": self.currency_usd.id,
                "foreign_rate": 0,
                "display_type": "line_note",
                "name": "Section Line",
            }
        )

        order.write(
            {
                "order_line": [order_line_01.id, order_line_02.id, order_line_03.id],
            }
        )
        return order

    def create_picking(self, trasfer_reason_code='external_storage'):
        reason_sale = self.env['transfer.reason'].search([('code', '=', trasfer_reason_code)], limit=1)

        warehouse = self.env['stock.warehouse'].search([('company_id', '=', self.company.id)], limit=1)
        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'outgoing'), 
            ('warehouse_id', '=', warehouse.id)
        ], limit=1)

        picking = self.env['stock.picking'].create({
            'partner_id': self.partner.id,
            'picking_type_id': picking_type.id,
            'location_id': picking_type.default_location_src_id.id,
            'location_dest_id': self.env.ref('stock.stock_location_customers').id,
            'origin': 'Manual Test Picking',
            'transfer_reason_id': reason_sale.id if reason_sale else False,
            'is_dispatch_guide': True,
        })

        self.env['stock.move'].create({
            'name': self.product.name,
            'product_id': self.product.id,
            'product_uom_qty': 10.0,
            'product_uom': self.product.uom_id.id,
            'picking_id': picking.id,
            'location_id': picking.location_id.id,
            'location_dest_id': picking.location_dest_id.id,
        })
        
        return picking

    def test_01_generate_invoice_from_dispatch_guide(self):
        order = self.create_sale_order()
        order.action_confirm()
        dispatch_guide = order.picking_ids

        for move in dispatch_guide.move_ids_without_package:
            move.quantity = move.product_uom_qty

        dispatch_guide.button_validate()

        invoice = dispatch_guide.create_invoice()

        self.assertTrue(
            len(invoice.invoice_line_ids) == len(order.order_line),
            "The invoice created from the sales orders dispatch guide must have the same number of lines as the sales order.",
        )
        _logger.info("test_01_generate_invoice_from_dispatch_guide --- successfully.")

    def test_02_generate_invoice_from_picking(self):
        picking = self.create_picking()
        
        for move in picking.move_ids_without_package:
            move.quantity = move.product_uom_qty
        picking.button_validate()

        self.assertTrue(picking.guide_number, "Debería tener un número de guía generado.")

        invoice = picking.create_invoice()

        self.assertEqual(invoice.move_type, 'out_invoice')
        self.assertEqual(len(invoice.invoice_line_ids), 1)
        
        line = invoice.invoice_line_ids[0]
        self.assertEqual(line.price_unit, self.product.list_price)
        
        self.assertEqual(picking.state_guide_dispatch, 'invoiced')
        _logger.info("test_02_generate_invoice_from_manual_picking --- successfully.")

    def test_03_generate_invoice_from_picking_maquila(self):
        """Verificar que al generar una factura desde un picking de maquila, no se creen líneas de factura y el estado del picking se actualice a 'invoiced'."""
        picking = self.create_picking("subcontracting")
        
        for move in picking.move_ids_without_package:
            move.quantity = move.product_uom_qty
        picking.button_validate()

        self.assertTrue(picking.guide_number, "Debería tener un número de guía generado.")

        invoice = picking.create_invoice()

        self.assertEqual(invoice.move_type, 'out_invoice')
        self.assertEqual(len(invoice.invoice_line_ids), 0, "No debería crear líneas de factura para movimientos de maquila.")

        self.assertEqual(picking.state_guide_dispatch, 'invoiced')
        _logger.info("test_03_generate_invoice_from_picking_maquila --- successfully.")

    def test_04_transfer_reason_subcontracting_config(self):
        """Verificar que la razón de Maquila se habilite/deshabilite según la compañía"""
        subcontracting_reason = self.env.ref("l10n_ve_stock_account.transfer_reason_subcontracting")
        
        # 2. Crear un picking interno (donde se aplica esta lógica)
        picking = self.create_picking()

        self.company.is_subcontracting = False
        picking._compute_allowed_reason_ids()
        
        self.assertNotIn(
            subcontracting_reason.id, 
            picking.allowed_reason_ids.ids,
            "La razón de Maquila NO debería estar en las permitidas si la configuración está apagada."
        )

        self.company.is_subcontracting = True
        picking._compute_allowed_reason_ids()
        
        self.assertIn(
            subcontracting_reason.id, 
            picking.allowed_reason_ids.ids,
            "La razón de Maquila DEBERÍA estar permitida cuando se activa en la compañía."
        )
        
        _logger.info("test_04_transfer_reason_subcontracting_config --- successfully.")
