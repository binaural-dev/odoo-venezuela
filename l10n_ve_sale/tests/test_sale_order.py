from odoo import _
from odoo.tests import Form
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError
from odoo.tests import tagged
import logging

_logger = logging.getLogger(__name__)

@tagged('post_install', '-at_install', 'l10n_ve_sale')
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
            'sequence': 10,
        })

        # Crear impuesto IVA 16%
        self.tax_iva16 = self.env['account.tax'].create({
            'name': 'IVA 16%',
            'amount': 16,
            'amount_type': 'percent',
            'type_tax_use': 'sale',
            'tax_group_id': self.tax_group.id,
            'country_id': self.env.ref('base.ve').id,
        })

        # Crear el producto
        self.product = self.env['product.product'].create({
            'name': 'Producto Prueba',
            'type': 'service',
            'list_price': 100,
            'barcode': '123456789',
            'taxes_id': [(6, 0, [self.tax_iva16.id])],
        })
        
        self.partner_a = self.env['res.partner'].create({
            'name': 'Test Partner A',
            'customer_rank': 1,
        })
        
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

        self.journal = self.env['account.journal'].create({
            'name': 'Diario de Ventas',
            'code': 'VEN',
            'type': 'sale',
            'sequence_id': sequence.id,
            "refund_sequence_id": refund_sequence.id,
            'company_id': self.env.company.id,
        })

    def test_01_generate_invoice_from_sale_order(self):
        rate = 5.0
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'manually_set_rate': True,
            'foreign_rate': rate,
            'foreign_inverse_rate': 1 / rate,
        })

        order_line_01 = self.env['sale.order.line'].create({
            'product_id': self.product.id,
            'product_uom_qty': 2,
            'price_unit': 100,
            'tax_id': [(6, 0, [self.tax_iva16.id])],
            'order_id': order.id,
            'currency_id': self.currency_vef.id,
            'foreign_currency_id': self.currency_usd.id,
            'foreign_rate': rate,
            'display_type': False,
            'name': 'Test Product Line',
        })

        order_line_02 = self.env['sale.order.line'].create({
            'product_id': False,
            'product_uom_qty': 0,
            'price_unit': 0,
            'tax_id': [(6, 0, [self.tax_iva16.id])],
            'order_id': order.id,
            'currency_id': self.currency_vef.id,
            'foreign_currency_id': self.currency_usd.id,
            'foreign_rate': 0,
            'display_type': 'line_section',
            'name': 'Section Line',
        })

        order_line_03 = self.env['sale.order.line'].create({
            'product_id': False,
            'product_uom_qty': 0,
            'price_unit': 0,
            'tax_id': [(6, 0, [self.tax_iva16.id])],
            'order_id': order.id,
            'currency_id': self.currency_vef.id,
            'foreign_currency_id': self.currency_usd.id,
            'foreign_rate': 0,
            'display_type': 'line_note',
            'name': 'Section Line',
        })

        order.write({
            'order_line': [order_line_01.id, order_line_02.id, order_line_03.id],
        })
        
        order.action_confirm()
        order._create_invoices()

    def test_02_error_generate_invoice_from_sale_order(self):
        rate = 5.0
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'manually_set_rate': True,
            'foreign_rate': rate,
            'foreign_inverse_rate': 1 / rate,
        })

        order_line_02 = self.env['sale.order.line'].create({
            'product_id': False,
            'product_uom_qty': 0,
            'price_unit': 0,
            'tax_id': [(6, 0, [self.tax_iva16.id])],
            'order_id': order.id,
            'currency_id': self.currency_vef.id,
            'foreign_currency_id': self.currency_usd.id,
            'foreign_rate': 0,
            'display_type': 'line_section',
            'name': 'Section Line',
        })

        order_line_03 = self.env['sale.order.line'].create({
            'product_id': False,
            'product_uom_qty': 0,
            'price_unit': 0,
            'tax_id': [(6, 0, [self.tax_iva16.id])],
            'order_id': order.id,
            'currency_id': self.currency_vef.id,
            'foreign_currency_id': self.currency_usd.id,
            'foreign_rate': 0,
            'display_type': 'line_note',
            'name': 'Section Line',
        })

        order.write({
            'order_line': [order_line_02.id, order_line_03.id],
        })
        
        with self.assertRaises(UserError) as e:
            order.action_confirm()
            order._create_invoices()
            _logger.info("Error generating invoice: %s", e.exception)
