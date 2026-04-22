from odoo import fields
from odoo.tests.common import TransactionCase
from odoo.tests import tagged

@tagged('post_install', '-at_install')
class TestSaleOrderForeignPricelist(TransactionCase):

    def setUp(self):
        super().setUp()
        company = self.env.ref('base.main_company')
        ves = self.env.ref('base.VES')
        usd = self.env.ref('base.USD')
        eur = self.env.ref('base.EUR')
        
        usd.write({'active': True})
        eur.write({'active': True})

        self.env['res.currency.rate'].search([
            ('currency_id', 'in', (usd.id, eur.id)),
            ('company_id', '=', company.id),
        ]).unlink()

        self.env['res.currency.rate'].create([
            {'name': '2026-01-01', 'currency_id': usd.id, 'rate': 1.0, 'company_id': company.id},
            {'name': '2026-01-01', 'currency_id': eur.id, 'rate': 0.9, 'company_id': company.id}
        ])
        company.currency_id = ves.id
        company.foreign_currency_id = usd.id

        self.env['res.currency.rate'].create([{
            'name': fields.Date.today(),
            'rate': 1.0,
            'currency_id': usd.id,
            'company_id': company.id,
        }, {
            'name': fields.Date.today(),
            'rate': 0.9,
            'currency_id': eur.id,
            'company_id': company.id,
        }])
        
        company.write({
            'currency_id': usd.id,
            'foreign_currency_id': eur.id,
        })

        pricelist_usd = self.env['product.pricelist'].create({
            'name': 'USD Pricelist',
            'currency_id': usd.id,
            'company_id': company.id,
        })

        # Crear producto
        product = self.env['product.product'].create({
            'name': 'Test Product',
            'list_price': 100,
        })

        # Crear partner
        partner = self.env['res.partner'].create({'name': 'Test Partner'})

        self.sale_order = self.env['sale.order'].create({
            'partner_id': partner.id,
            'pricelist_id': pricelist_usd.id,
            'order_line': [(0, 0, {
                'product_id': product.id,
                'product_uom_qty': 2,
                'price_unit': 100,
            })],
        })

    def test_totals_and_conversion(self):
        self.sale_order.action_confirm()
        self.assertEqual(self.sale_order.pricelist_id.currency_id.name, 'USD')
        
        # Total in Base Currency (USD)
        total_usd = self.sale_order.amount_total
        self.assertEqual(total_usd, 200)
        
        # Expected Foreign Total in EUR (Rate 1 USD = 0.9 EUR)
        # 200 USD * 0.9 = 180 EUR
        expected_eur = total_usd * 0.9
        
        # foreign_total_billed should be in EUR
        self.assertAlmostEqual(self.sale_order.foreign_total_billed, expected_eur, places=2)