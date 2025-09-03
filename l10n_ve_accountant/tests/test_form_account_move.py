from odoo.tests import TransactionCase, tagged, Form
from odoo import fields
import logging
_logger = logging.getLogger(__name__)


@tagged('post_install', '-at_install', 'l10n_ve_accountant')
class TestFormAccountMove(TransactionCase):
    def setUp(self):
        partner_model = self.env['res.partner']
        self.invoice_model = self.env['account.move']

        self.partner_a = self.env['res.partner'].create({
            'name': 'Test Partner A',
            'customer_rank': 1,
        })
        
        self.currency_usd = self.env.ref("base.USD")
        self.currency_vef = self.env.ref("base.VEF")
        self.company = self.env.ref("base.main_company")
        self.company.write(
            {
                "currency_id": self.currency_usd.id,
                "currency_foreign_id": self.currency_vef.id,
            }
        )
        self.invoice_model.create({
            'move_type': 'in_invoice',
            'foreign_rate': 1.23,
            'partner_id': self.partner_a.id
        })
        self.date = fields.Date.today()

    def test_foreign_rate_editable_only_on_in_invoice(self):
        self.assertTrue(self.company.currency_foreign_id, 'Foreign currency should be set for the company.')
        invoice_form = self.env['account.move'].with_context(default_move_type='in_invoice').new()
        invoice_form.company_id = self.company.id
        invoice_form.currency_id = self.currency_usd
        invoice_form.foreign_currency_id = self.currency_vef
        invoice_form.partner_id = self.partner_a
        invoice_form.invoice_date = self.date
        invoice_form.foreign_rate = 1.23

        self.assertEqual(invoice_form.foreign_rate, 1.23, 'Foreign rate should be set to 1.23 for in_invoice move type.')
    
    def test_foreign_rate_editable_only_on_in_invoice_case_customer(self):
        self.assertTrue(self.company.currency_foreign_id, 'Foreign currency should be set for the company.')
        invoice_form = self.env['account.move'].with_context(default_move_type='out_invoice').new()
        invoice_form.company_id = self.company.id
        invoice_form.currency_id = self.currency_usd
        invoice_form.foreign_currency_id = self.currency_vef
        invoice_form.partner_id = self.partner_a
        invoice_form.invoice_date = self.date
        self.assertNotEqual(invoice_form.foreign_rate, 1.23, 'Foreign rate should be set to 1.23 for in_invoice move type.')
