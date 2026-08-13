from odoo.tests.common import TransactionCase
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestActionConfirmServiceProducts(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.partner = self.env['res.partner'].create({'name': 'Test Partner'})
        self.service_product = self.env['product.product'].create({
            'name': 'Service Product',
            'type': 'service',
            'list_price': 50.0,
        })
        self.storable_product = self.env['product.product'].create({
            'name': 'Storable Product',
            'type': 'consu',
            'list_price': 100.0,
        })

    def test_confirm_service_only(self):
        """T6: SO con solo producto servicio → confirm exitoso, 0 pickings."""
        sale_order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [(0, 0, {
                'product_id': self.service_product.id,
                'product_uom_qty': 1,
                'price_unit': 50.0,
            })],
        })
        sale_order.action_confirm()
        self.assertEqual(sale_order.state, 'sale')
        self.assertEqual(len(sale_order.picking_ids), 0)

    def test_confirm_mixed_products(self):
        """T7: SO con 1 servicio + 1 storable → confirm exitoso, pickings solo para storable."""
        sale_order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [
                (0, 0, {
                    'product_id': self.service_product.id,
                    'product_uom_qty': 1,
                    'price_unit': 50.0,
                }),
                (0, 0, {
                    'product_id': self.storable_product.id,
                    'product_uom_qty': 1,
                    'price_unit': 100.0,
                }),
            ],
        })
        sale_order.action_confirm()
        self.assertEqual(sale_order.state, 'sale')
        self.assertEqual(len(sale_order.picking_ids), 1)

    def test_confirm_storable_with_split(self):
        """T8: SO con 5 storable, limit=2 → 3 pickings (2+2+1)."""
        self.company.limit_product_qty_out = 2
        products = self.env['product.product'].create([
            {'name': f'Storable Product {i}', 'type': 'consu', 'list_price': 10.0}
            for i in range(5)
        ])
        sale_order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [
                (0, 0, {
                    'product_id': p.id,
                    'product_uom_qty': 1,
                    'price_unit': 10.0,
                })
                for p in products
            ],
        })
        sale_order.action_confirm()
        self.assertEqual(sale_order.state, 'sale')
        self.assertEqual(len(sale_order.picking_ids), 3)

    def test_confirm_limit_zero(self):
        """T9: SO con storable, limit=0 → 1 picking sin dividir."""
        self.company.limit_product_qty_out = 0
        sale_order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [(0, 0, {
                'product_id': self.storable_product.id,
                'product_uom_qty': 1,
                'price_unit': 100.0,
            })],
        })
        sale_order.action_confirm()
        self.assertEqual(sale_order.state, 'sale')
        self.assertEqual(len(sale_order.picking_ids), 1)
