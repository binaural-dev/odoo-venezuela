from odoo.tests.common import TransactionCase
from odoo.tests import tagged
from odoo import fields
from datetime import timedelta
import logging

_logger = logging.getLogger(__name__)

@tagged("post_install", "-at_install", "l10n_ve_sale")
class TestSaleOrderRate(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company = self.env.company
        
        # Ensure distinct currencies
        self.ves = self.env.ref('base.VEF')
        self.usd = self.env.ref('base.USD')
        
        # Setup Company Currency (VES)
        self.company.currency_id = self.ves

        # Setup Foreign Currency (USD) for the test
        self.company.foreign_currency_id = self.usd
        
        self.today = fields.Date.today()
        
        # Create a rate for USD
        # 1 USD = 380 VES
        self.usd_rate_val = 1.0 / 380.0
        self.usd_rate = self.env['res.currency.rate'].create({
            'currency_id': self.usd.id,
            'company_id': self.company.id,
            'name': self.today,
            'rate': self.usd_rate_val, 
        })
        
        # Create a rate for EUR
        # 1 EUR = 400 VES
        self.eur = self.env.ref("base.EUR")
        self.eur_rate_val = 1.0 / 400.0
        self.eur_rate = self.env['res.currency.rate'].create({
            'currency_id': self.eur.id,
            'company_id': self.company.id,
            'name': self.today,
            'rate': self.eur_rate_val,
        })
        
        # Partner + Product
        
        # Partner + Product
        self.partner = self.env['res.partner'].create({'name': 'Test Partner'})
        self.product = self.env['product.product'].create({
            'name': 'Test Product',
            'list_price': 100.0, # in VES
        })

    def test_default_rate_assignment(self):
        """ Test that creating a sale order correctly fetches the foreign rate for USD """

        so = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'date_order': self.today,
        })
        _logger.info("Verifying Foreign Rate assignments...")
        _logger.info("Sale Order Foreign Rate: %s (Should be > 1.0 and != 1.0 for EUR)", so.foreign_rate)
        _logger.info("Sale Order Foreign Inverse Rate: %s", so.foreign_inverse_rate)
        
        # Let's assert it is NOT 1.0
        _logger.info("Verifying Foreign Rate assignments...")
        _logger.info("Sale Order Foreign Rate: %s (Should be ~380 for USD)", so.foreign_rate)
        _logger.info("Sale Order Foreign Inverse Rate: %s", so.foreign_inverse_rate)
        
        # User Expectation:
        # Rate = 1/380
        # foreign_rate (VES per USD) = 380.0
        # foreign_inverse_rate (USD per VES) = 1/380.0
        
        self.assertNotEqual(so.foreign_rate, 1.0, "Foreign rate should not default to 1.0 for USD")
        self.assertAlmostEqual(so.foreign_rate, 380.0, places=2, msg="Foreign rate should be 380")
        self.assertAlmostEqual(so.foreign_inverse_rate, 1.0/380.0, places=6, msg="Foreign inverse rate should be 1/380")

    def test_foreign_price_computation(self):
        """ Test that lines compute foreign_price correctly """
        
        # Create SO
        so = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'date_order': self.today,
        })
        
        line = self.env['sale.order.line'].create({
            'order_id': so.id,
            'product_id': self.product.id,
            'product_uom_qty': 1,
            'price_unit': 100.0, # 100 VES
        })
        
        # Trigger computations
        line._compute_foreign_price()
        
        expected_foreign_price = 100.0 * so.foreign_inverse_rate
        
        _logger.info("Testing Foreign Price Computation (VES Context)...")
        _logger.info("Line Price Unit (VES): %s", line.price_unit)
        _logger.info("Applicable Foreign Inverse Rate: %s", so.foreign_inverse_rate)
        _logger.info("Computed Foreign Price: %s", line.foreign_price)
        _logger.info("Expected Foreign Price: %s", expected_foreign_price)
        
        self.assertAlmostEqual(line.foreign_price, expected_foreign_price, places=2, 
                               msg="Foreign price should be price_unit * foreign_inverse_rate when SO is in VES")
        
        # Case 2: SO is in Foreign Currency (USD)
        # If I change SO currency to USD.
        so.currency_id = self.usd
        line.price_unit = 50.0 # 50 USD
        
        # Logic in sale_order_line:
        # elif line.currency_id.id == foreign_currency.id:
        #    line.foreign_price = line.price_unit
        
        line._compute_foreign_price()
        
        _logger.info("Testing Foreign Price Computation (USD Context)...")
        _logger.info("Line Price Unit (USD): %s", line.price_unit)
        _logger.info("Computed Foreign Price (Should be equal to Price Unit): %s", line.foreign_price)
        
        self.assertEqual(line.foreign_price, 50.0)
        
    def test_eur_so_foreign_price(self):
        """ Test that an SO in EUR computes foreign price (in USD) correctly """
        _logger.info("[TEST] Iniciando test_eur_so_foreign_price")
        # Create EUR Pricelist to ensure SO stays in EUR
        pricelist_eur = self.env['product.pricelist'].create({
            'name': 'EUR Pricelist',
            'currency_id': self.eur.id,
        })
        _logger.info(f"[TEST] EUR Pricelist creado: {pricelist_eur}")
        # SO in EUR
        so = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'date_order': self.today,
            'pricelist_id': pricelist_eur.id,
            'currency_id': self.eur.id
        })
        _logger.info(f"[TEST] Sale Order creado en EUR: {so}")
        _logger.info(f"[TEST] SO.foreign_currency_id: {so.foreign_currency_id}")
        _logger.info(f"[TEST] SO.foreign_rate: {so.foreign_rate}")
        # The foreign rate should still be USD Check
        self.assertAlmostEqual(so.foreign_rate, 380.0, places=2)
        line = self.env['sale.order.line'].create({
            'order_id': so.id,
            'product_id': self.product.id,
            'product_uom_qty': 1,
            'price_unit': 100.0, # 100 EUR
        })
        _logger.info(f"[TEST] Sale Order Line creado: {line}")
        _logger.info(f"[TEST] Line.price_unit: {line.price_unit}")
        # Logic: 100 EUR -> VES -> USD
        # 100 EUR * 400 (VES/EUR) = 40,000 VES
        # 40,000 VES * (1/380) (USD/VES) = 105.263... USD
        line._compute_foreign_price()
        _logger.info(f"[TEST] Line.foreign_price después de _compute_foreign_price: {line.foreign_price}")
        expected_ves = 100.0 * 400.0 # simplified expectation based on rates
        expected_usd = expected_ves * (1.0 / 380.0)
        _logger.info(f"[TEST] expected_ves: {expected_ves}")
        _logger.info(f"[TEST] expected_usd: {expected_usd}")
        self.assertAlmostEqual(line.foreign_price, expected_usd, delta=0.1)

    def test_amount_signed(self):
        """ Test that amount_untaxed_total_signed and amount_total_signed are computed correctly """
        
        # Create USD Pricelist
        pricelist_usd = self.env['product.pricelist'].create({
            'name': 'USD Pricelist',
            'currency_id': self.usd.id,
        })

        # Create Sale Order in USD (Foreign Currency) using the pricelist
        so = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'date_order': self.today,
            'pricelist_id': pricelist_usd.id,
        })
        
        # Add Order Line
        # Price Unit = 100 USD
        line = self.env['sale.order.line'].create({
            'order_id': so.id,
            'product_id': self.product.id,
            'product_uom_qty': 1,
            'price_unit': 100.0,
        })
        
        # Trigger computations
        # The fields are computed, so we might need to flush or trigger recompute if not automatic
        # accessing them should trigger compute
        
        _logger.info("Testing Amount Signed Computation...")
        _logger.info("SO Currency: %s", so.currency_id.name)
        _logger.info("Company Currency: %s", so.company_id.currency_id.name)
        _logger.info("Amount Untaxed: %s", so.amount_untaxed)
        _logger.info("Amount Total: %s", so.amount_total)
        
        # Conversion Rate USD -> VES is 380 (1/380 inverse)
        # 100 USD * 380 = 38000 VES
        
        expected_amount_signed = 100.0 * 380.0
        
        _logger.info("Amount Untaxed Signed: %s", so.amount_untaxed_total_signed)
        _logger.info("Amount Total Signed: %s", so.amount_total_signed)
        _logger.info("Expected Amount Signed: %s", expected_amount_signed)
        
        self.assertAlmostEqual(so.amount_untaxed_total_signed, expected_amount_signed, delta=1.0, 
                               msg="Amount Untaxed Signed should be Amount Untaxed converted to Company Currency")
        self.assertAlmostEqual(so.amount_total_signed, expected_amount_signed, delta=1.0,
                               msg="Amount Total Signed should be Amount Total converted to Company Currency")
                               
        # Case 2: SO in Company Currency (VES)
        so_ves = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'date_order': self.today,
            'currency_id': self.ves.id,
        })
        
        line_ves = self.env['sale.order.line'].create({
            'order_id': so_ves.id,
            'product_id': self.product.id,
            'product_uom_qty': 1,
            'price_unit': 40000.0, # 40000 VES
        })
        
        _logger.info("Testing Amount Signed Computation (VES Context)...")
        _logger.info("Amount Untaxed Signed (VES): %s", so_ves.amount_untaxed_total_signed)
        
        self.assertEqual(so_ves.amount_untaxed_total_signed, 40000.0, 
                         msg="Amount Untaxed Signed should be equal to Amount Untaxed when Currency is Company Currency")


