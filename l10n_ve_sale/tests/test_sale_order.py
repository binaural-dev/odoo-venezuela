from odoo import _
from odoo.tests import Form
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError
from odoo.tests import tagged
import logging

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "l10n_ve_sale")
class TestSaleOrderInvoice(TransactionCase):
    """Tests for generating invoices from sale orders in Venezuelan localization."""

    def setUp(self):
        super(TestSaleOrderInvoice, self).setUp()
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
                "type": "service",
                "list_price": 100,
                "barcode": "123456789",
                "taxes_id": [(6, 0, [self.tax_iva16.id])],
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
            }
        )

    def test_01_generate_invoice_from_sale_order(self):
        rate = 5.0
        order = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "manually_set_rate": True,
                "foreign_rate": rate,
                "foreign_inverse_rate": 1 / rate,
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

        order.action_confirm()
        invoice = order._create_invoices()

        self.assertTrue(
            len(order.order_line) == len(invoice.invoice_line_ids),
            "The invoice created from the sales order must have the same number of lines as the sales order.",
        )
        _logger.info("test_01_generate_invoice_from_sale_order --- successfully")

    def test_02_error_generate_invoice_from_sale_order(self):
        rate = 5.0
        order = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "manually_set_rate": True,
                "foreign_rate": rate,
                "foreign_inverse_rate": 1 / rate,
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
                "order_line": [order_line_02.id, order_line_03.id],
            }
        )

        with self.assertRaises(UserError) as e:
            order.action_confirm()
            order._create_invoices()
        _logger.info("test_02_error_generate_invoice_from_sale_order --- successfully (%s)",e.exception,)

    def test_03_reconfirm_sale_order_with_pickings(self):
        """Test reconfirming a sale order after it was confirmed, cancelled and set to draft.
        This flow was causing a singleton error in stock.picking.
        """
        # Create a storable product
        product_storable = self.env["product.product"].create({
            "name": "Producto Almacenable",
            "type": "product",
            "invoice_policy": "order",
            "list_price": 50,
            "taxes_id": [(6, 0, [self.tax_iva16.id])],
            "barcode": "ST12345",
        })
        
        # Give some stock
        warehouse = self.env['stock.warehouse'].search([('company_id', '=', self.company.id)], limit=1)
        self.env['stock.quant'].with_context(inventory_mode=True).create({
            'product_id': product_storable.id,
            'location_id': warehouse.lot_stock_id.id,
            'inventory_quantity': 10,
        }).action_apply_inventory()

        rate = 5.0
        # Create order with 2 lines of 1 unit each to trigger split picking logic
        order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "manually_set_rate": True,
            "foreign_rate": rate,
            "foreign_inverse_rate": 1 / rate,
            "order_line": [
                (0, 0, {
                    "product_id": product_storable.id,
                    "product_uom_qty": 1,
                    "price_unit": 100,
                    "tax_id": [(6, 0, [self.tax_iva16.id])],
                    "name": "Line 1",
                }),
                (0, 0, {
                    "product_id": product_storable.id,
                    "product_uom_qty": 1,
                    "price_unit": 100,
                    "tax_id": [(6, 0, [self.tax_iva16.id])],
                    "name": "Line 2",
                })
            ]
        })

        # Seteamos el límite de pickings para que se dividan
        self.company.write({'limit_product_qty_out': 1})

        # 1. Confirm the order
        order.action_confirm()
        self.assertEqual(order.state, 'sale')
        self.assertTrue(len(order.picking_ids) > 1, "Should have created multiple pickings due to limit_product_qty_out=1")
        
        # 2. Cancel related pickings to allow SO cancellation
        for picking in order.picking_ids:
            picking.move_ids.write({'state': 'cancel'})
            picking.write({'state': 'cancel'})
        
        # 3. Cancel the order
        order.action_cancel()
        if order.state != 'cancel':
            order.write({'state': 'cancel'})
            
        self.assertEqual(order.state, 'cancel')
        
        # 4. Set back to draft
        order.action_draft()
        self.assertEqual(order.state, 'draft')
        
        # 5. Confirm again (This validates the fix for the singleton error)
        order.action_confirm()
        self.assertEqual(order.state, 'sale')
        _logger.info("test_03_reconfirm_sale_order_with_pickings --- successfully")
