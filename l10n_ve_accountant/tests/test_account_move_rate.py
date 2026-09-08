from odoo import fields
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

    def test_compute_rate_updates_new_record_without_saving(self):
        """Regression: _compute_rate_for_documents must assign foreign_rate/
        foreign_inverse_rate directly instead of calling move.write({...}).
        write() is a no-op on NewId (onchange-preview) records, so the old code
        left the recomputed rate invisible in the form until the user saved.
        """
        self.env["res.currency.rate"].create({
            "name": fields.Date.today(),
            "currency_id": self.currency_vef.id,
            "company_rate": 42.5,
            "company_id": self.company.id,
        })
        partner = self.env["res.partner"].create({"name": "Cliente Rate Preview"})

        move_form = self.env["account.move"].with_context(default_move_type="out_invoice").new()
        move_form.company_id = self.company.id
        move_form.currency_id = self.currency_usd
        move_form.foreign_currency_id = self.currency_vef
        move_form.partner_id = partner
        move_form.invoice_date = fields.Date.today()

        self.assertEqual(
            move_form.foreign_rate,
            42.5,
            "The onchange preview must reflect the recomputed foreign_rate without "
            "saving; a move.write() inside the compute method silently no-ops on "
            "NewId records.",
        )

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