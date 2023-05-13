from odoo.tests.common import TransactionCase
from odoo import fields


class TestPurchaseOrder(TransactionCase):
    def setUp(self):
        super().setUp()

        self.currency_vef = self.env.ref('base.VEF')

        self.product_template = self.env['product.template'].create({
            'name': 'Test Product Template',
            'list_price': 10.0,
            'standard_price': 5.0,
        })

        self.product = self.env['product.product'].create({
            'product_tmpl_id': self.product_template.id,
            'name': 'Test Product',
        })

        self.purchase_order = self.env['purchase.order'].create({
            'partner_id': self.env.ref('base.res_partner_2').id,
            'date_order': fields.Date.today(),
            'currency_id': self.currency_vef.id,
        })

        self.purchase_order_line = self.env['purchase.order.line'].create({
            'order_id': self.purchase_order.id,
            'product_id': self.product.id,
            'product_qty': 1,
            'price_unit': 7.0,
            'update_latest_standard_price': True,
        })

    def test_button_confirm(self):
        # Test that the latest standard price and last_latest_standard_price fields are updated correctly
        self.assertEqual(self.product.latest_standard_price, 5.0)
        self.assertEqual(self.product.last_latest_standard_price, 5.0)
        self.assertEqual(self.purchase_order_line.latest_standard_price, 7.0)
        self.purchase_order.button_confirm()
        self.assertEqual(self.product.latest_standard_price, 7.0)
        self.assertEqual(self.product.last_latest_standard_price, 5.0)
        self.assertEqual(self.product.product_tmpl_id.latest_standard_price, 7.0)
        self.assertEqual(self.product.product_tmpl_id.last_latest_standard_price, 5.0)

    def test_button_cancel(self):
        # Test that the latest standard price field is updated correctly when the order is cancelled
        self.purchase_order.button_confirm()
        self.purchase_order.button_cancel()
        self.assertEqual(self.product.latest_standard_price, 5.0)
        self.assertEqual(self.product.product_tmpl_id.latest_standard_price, 5.0)

    def test_get_lines_with_updatable_latest_standard_price(self):
        # Test that the function returns the correct lines to update
        purchase_order_line2 = self.env['purchase.order.line'].create({
            'order_id': self.purchase_order.id,
            'product_id': self.product.id,
            'product_qty': 1,
            'price_unit': 8.0,
            'update_latest_standard_price': False,
        })
        lines = self.purchase_order._get_lines_with_updatable_latest_standard_price()
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0], self.purchase_order_line)