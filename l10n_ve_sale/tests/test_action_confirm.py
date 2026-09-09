from odoo import fields
from odoo.exceptions import ValidationError
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


@tagged('post_install', '-at_install')
class TestActionConfirmCreditLimit(TransactionCase):
    """Cobertura del fix de alcance: el chequeo de crédito estaba anidado
    dentro de `if not_allow_sell_products`, así que con la configuración
    por defecto de compañía (`not_allow_sell_products=False`) nunca corría.
    Ver openspec/changes/l10n-ve-sale-credit-limit-block-scope-fix.
    """

    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.company.account_use_credit_limit = True
        # l10n_ve_accountant calcula siempre un total en "moneda alterna"
        # (`_get_tax_totals_summary`) al leer `order.amount_total`, y esa
        # ruta revienta si la compañía no tiene `foreign_currency_id` con
        # una tasa activa. En cualquier compañía VE real esto ya está
        # configurado (es lo que usa `l10n_ve_rate`); acá se replica esa
        # condición para no depender de un bug ajeno a este fix.
        foreign_currency = self.env.ref('base.EUR')
        foreign_currency.active = True
        self.company.foreign_currency_id = foreign_currency
        self.env['res.currency.rate'].create({
            'currency_id': foreign_currency.id,
            'company_id': self.company.id,
            'name': fields.Date.today(),
            'rate': 1.1,
        })
        self.partner = self.env['res.partner'].create({
            'name': 'Credit Limit Partner',
            'use_partner_credit_limit_order': True,
            'credit_limit': 100.0,
        })
        self.product = self.env['product.product'].create({
            'name': 'Expensive Product',
            'type': 'service',
            'list_price': 500.0,
        })

    def _create_order(self):
        return self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 1,
                'price_unit': 500.0,
            })],
        })

    def test_blocks_over_limit_with_default_company_settings(self):
        self.company.not_allow_sell_products = False
        order = self._create_order()
        with self.assertRaises(ValidationError):
            order.action_confirm()

    def test_stock_setting_does_not_change_credit_result(self):
        self.company.not_allow_sell_products = True
        order = self._create_order()
        with self.assertRaises(ValidationError):
            order.action_confirm()

    def test_skip_credit_limit_check_bypasses_block(self):
        self.company.not_allow_sell_products = False
        order = self._create_order()
        order.with_context(skip_credit_limit_check=True).action_confirm()
        self.assertEqual(order.state, 'sale')

    def test_company_flag_off_never_blocks(self):
        self.company.account_use_credit_limit = False
        order = self._create_order()
        order.action_confirm()
        self.assertEqual(order.state, 'sale')
