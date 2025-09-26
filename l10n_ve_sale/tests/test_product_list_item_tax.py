from odoo.tests import TransactionCase, tagged
from odoo.exceptions import ValidationError

@tagged('post_install', '-at_install', 'l10n_ve_sale')
class TestProductPricelistItemTax(TransactionCase):

    def setUp(self):
        super().setUp()
        self.currency = self.env.ref('base.main_company').currency_id
        self.tax = self.env['account.tax'].create({
            'name': 'IVA 16%',
            'amount': 16.0,
            'type_tax_use': 'sale',
        })
        self.product_tmpl = self.env['product.template'].create({
            'name': 'Producto Test',
            'list_price': 100.0,
            'uom_id': self.env.ref('uom.product_uom_unit').id,
            'uom_po_id': self.env.ref('uom.product_uom_unit').id,
            'taxes_id': [(6, 0, [self.tax.id])],
        })
        self.pricelist = self.env['product.pricelist'].create({
            'name': 'Lista Test',
            'currency_id': self.currency.id,
        })
        self.product_no_tax = self.env['product.template'].create({
            'name': 'Producto Sin IVA',
            'list_price': 50.0,
            'uom_id': self.env.ref('uom.product_uom_unit').id,
            'uom_po_id': self.env.ref('uom.product_uom_unit').id,
            # Sin impuestos
        })

    def test_compute_prices_with_tax_with_taxes(self):
        item = self.env['product.pricelist.item'].create({
            'pricelist_id': self.pricelist.id,
            'product_tmpl_id': self.product_tmpl.id,
            'fixed_price': 100.0,
            'currency_id': self.currency.id,
        })
        # IVA 16%: total_included = 116, total_excluded = 100
        self.assertAlmostEqual(item.price_without_tax, 100.0)
    
    def test_compute_prices_with_tax_no_tax(self):
        item = self.env['product.pricelist.item'].create({
            'pricelist_id': self.pricelist.id,
            'product_tmpl_id': self.product_tmpl.id,
            'fixed_price': 50.0,
            'currency_id': self.currency.id,
        })
        # Si el producto no tiene impuestos, price_with_tax y price_without_tax deben ser iguales al fixed_price
        self.assertEqual(item.price_without_tax, 50.0)
        self.assertEqual(item.price_with_tax, 58.0)
    

    def test_fixed_price_negative_raises(self):
        with self.assertRaises(ValidationError):
            self.env['product.pricelist.item'].create({
                'pricelist_id': self.pricelist.id,
                'product_tmpl_id': self.product_tmpl.id,
                'fixed_price': -5.0,
                'currency_id': self.currency.id,
            })

    def test_fixed_price_zero_ok(self):
        item = self.env['product.pricelist.item'].create({
            'pricelist_id': self.pricelist.id,
            'product_tmpl_id': self.product_tmpl.id,
            'fixed_price': 0.0,
            'currency_id': self.currency.id,
        })
        self.assertEqual(item.fixed_price, 0.0)

    def test_fixed_price_positive_ok(self):
        item = self.env['product.pricelist.item'].create({
            'pricelist_id': self.pricelist.id,
            'product_tmpl_id': self.product_tmpl.id,
            'fixed_price': 10.0,
            'currency_id': self.currency.id,
        })
        self.assertEqual(item.fixed_price, 10.0)

    
    def test_compute_prices_with_tax_with_taxes(self):
        item = self.env['product.pricelist.item'].create({
            'pricelist_id': self.pricelist.id,
            'product_tmpl_id': self.product_tmpl.id,
            'fixed_price': 100.0,
            'currency_id': self.currency.id,
        })
        # IVA 16%: total_included = 116, total_excluded = 100
        self.assertAlmostEqual(item.price_without_tax, 100.0)
        self.assertAlmostEqual(item.price_with_tax, 116.0)

    def test_compute_prices_with_tax_without_taxes(self):
        item = self.env['product.pricelist.item'].create({
            'pricelist_id': self.pricelist.id,
            'product_tmpl_id': self.product_no_tax.id,
            'fixed_price': 50.0,
            'currency_id': self.currency.id,
        })
        self.assertAlmostEqual(item.price_without_tax, 50.0)
        self.assertAlmostEqual(item.price_with_tax, 57.5)

    def test_compute_prices_with_tax_no_product(self):
        item = self.env['product.pricelist.item'].create({
            'pricelist_id': self.pricelist.id,
            'fixed_price': 80.0,
            'currency_id': self.currency.id,
        })
        self.assertAlmostEqual(item.price_without_tax, 80.0)
        self.assertAlmostEqual(item.price_with_tax, 80.0)