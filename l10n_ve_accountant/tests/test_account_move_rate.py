from odoo.tests import TransactionCase, tagged

@tagged("post_install", "-at_install", "l10n_ve_accountant", "rate_decimal_precision")
class TestAccountMoveRate(TransactionCase):

    def setUp(self):
        super().setUp()
        self.currency_usd = self.env.ref("base.USD")
        self.currency_vef = self.env.ref("base.VEF")
        self.company = self.env.ref("base.main_company")
        self.company.write({
            "currency_id": self.currency_usd.id,
            "currency_foreign_id": self.currency_vef.id,
        })
    
    def test_foreign_rate_decimal_precision(self):
        """
        Test that the foreign_rate field uses the 'Tasa' decimal precision
        and updates accordingly when the precision is changed.
        """
        tasa_precision = self.env['decimal.precision'].search([('name', '=', 'Tasa')], limit=1)
        self.assertTrue(tasa_precision, "Decimal precision 'Tasa' not found")

        tasa_precision.digits = 4
        
        # In Odoo, field parameters usually are cached or computed. 
        # For 'digits' using a string (like 'Tasa'), it delegates to decimal.precision.
        # We need to check if the field 'foreign_rate' on account.move respects this.
        
        foreign_rate_field = self.env['account.move']._fields['foreign_rate']
        
        precision = foreign_rate_field.get_digits(self.env)
        self.assertEqual(precision, (16, 4), "foreign_rate precision should be (16, 4)")
        
        tasa_precision.digits = 6
        
        precision = foreign_rate_field.get_digits(self.env)
        self.assertEqual(precision, (16, 6), "foreign_rate precision should be (16, 6)")