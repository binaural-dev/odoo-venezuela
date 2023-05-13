from odoo.tests.common import TransactionCase
from odoo import fields


class TestPurchaseOrderLine(TransactionCase):
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
        })

    def test_compute_latest_standard_price(self):
        # Test that the latest standard price is correctly computed
        self.assertEqual(self.purchase_order_line.latest_standard_price, 5.0)
        self.product_template.write({'standard_price': 8.0})
        self.assertEqual(self.purchase_order_line.latest_standard_price, 8.0)

    def test_onchange_update_latest_standard_price(self):
        # Test that the update_latest_standard_price field is set to True when the price unit is greater than the latest standard price
        self.assertFalse(self.purchase_order_line.update_latest_standard_price)
        self.purchase_order_line.price_unit = 10.0
        self.assertTrue(self.purchase_order_line.update_latest_standard_price)