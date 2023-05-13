from odoo.tests.common import TransactionCase
from odoo import fields


class TestProductTemplate(TransactionCase):
    def setUp(self):
        super().setUp()

        self.product_template = self.env['product.template'].create({
            'name': 'Test Product Template',
            'list_price': 10.0,
            'standard_price': 5.0,
        })

        self.product = self.env['product.product'].create({
            'product_tmpl_id': self.product_template.id,
            'name': 'Test Product',
        })

    def test_compute_latest_standard_price(self):
        # Test that the latest standard price is correct when there is only one variant
        self.assertEqual(self.product_template.latest_standard_price, 5.0)
        self.product_template.write({'standard_price': 7.0})
        self.assertEqual(self.product_template.latest_standard_price, 7.0)

        # Test that the latest standard price is 0 when there are no variants
        product_template = self.env['product.template'].create({
            'name': 'Test Product Template 2',
            'list_price': 10.0,
            'standard_price': 5.0,
        })
        self.assertEqual(product_template.latest_standard_price, 0.0)

    def test_compute_variants_are_active(self):
        # Test that the function returns True when the user has the 'product.group_product_variant' group
        user = self.env['res.users'].create({
            'name': 'Test User',
            'login': 'testuser',
            'groups_id': [(4, self.env.ref('product.group_product_variant').id)],
        })
        self.env = self.env(user=user.id)
        self.assertTrue(self.env['product.template'].variants_are_active)

        # Test that the function returns False when the user does not have the 'product.group_product_variant' group
        user.groups_id = [(3, self.env.ref('product.group_product_variant').id)]
        self.assertFalse(self.env['product.template'].variants_are_active)