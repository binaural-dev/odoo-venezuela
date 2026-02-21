from odoo.tests.common import TransactionCase

class TestSaleOrderForeignPricelist(TransactionCase):

    def setUp(self):
        super().setUp()
        company = self.env.ref('base.main_company')
        usd = self.env['res.currency'].create({'name': 'USD', 'symbol': '$', 'rate': 1.0})
        eur = self.env['res.currency'].create({'name': 'EUR', 'symbol': '€', 'rate': 0.9})
        company.currency_id = usd.id

        pricelist_eur = self.env['product.pricelist'].create({
            'name': 'EUR Pricelist',
            'currency_id': eur.id,
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
            'pricelist_id': pricelist_eur.id,
            'order_line': [(0, 0, {
                'product_id': product.id,
                'product_uom_qty': 2,
                'price_unit': 100,
            })],
        })

    def test_totals_and_conversion(self):
        self.sale_order.action_confirm()
        self.assertEqual(self.sale_order.pricelist_id.currency_id.name, 'EUR')
        total_eur = self.sale_order.amount_total
        self.assertEqual(total_eur, 200)
        rate = self.sale_order.pricelist_id.currency_id.rate / self.sale_order.company_id.currency_id.rate
        total_usd = total_eur / rate
        self.assertAlmostEqual(self.sale_order.foreign_total_billed, total_usd, places=2)