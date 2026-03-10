from odoo.tests import TransactionCase, tagged
from odoo import fields
import logging

_logger = logging.getLogger(__name__)

@tagged("post_install", "-at_install", "l10n_ve_accountant_payment_rate")
class TestAccountPaymentRate(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company = self.env.ref("base.main_company")
        self.env.user.write({'company_ids': [(4, self.company.id)], 'company_id': self.company.id})
        self.currency_vef = self.env.ref("base.VEF")
        self.currency_usd = self.env.ref("base.USD")
        self.currency_eur = self.env.ref("base.EUR")
        
        # Configure Company
        # Main currency: VEF
        # Secondary currency: USD
        self.company.write({
            "currency_id": self.currency_vef.id,
            "foreign_currency_id": self.currency_usd.id,
        })
        
        # Helpers
        self.Rate = self.env["res.currency.rate"]
        self.today = fields.Date.today()

        _logger.warning(f"SETUP: Company ID: {self.company.id}")
        _logger.warning(f"SETUP: Currency VEF: {self.currency_vef.id}")
        _logger.warning(f"SETUP: Currency USD: {self.currency_usd.id}")
        _logger.warning(f"SETUP: Currency EUR: {self.currency_eur.id} (Active: {self.currency_eur.active})")
        
        # Ensure EUR is active
        if not self.currency_eur.active:
             self.currency_eur.active = True

        # Set up Rates
        # 1 USD = 40 VEF
        self.rate_usd = self.Rate.create({
            "name": self.today,
            "currency_id": self.currency_usd.id,
            "company_id": self.company.id,
            "company_rate": 1.0 / 40.0,
            "inverse_company_rate": 40.0,
        })
        
        # 1 EUR = 45 VEF
        self.rate_eur = self.Rate.create({
            "name": self.today,
            "currency_id": self.currency_eur.id,
            "company_id": self.company.id,
            "company_rate": 1.0 / 45.0,
            "inverse_company_rate": 45.0,
        })
        _logger.warning(f"SETUP: Created Rate EUR: {self.rate_eur.id} for Currency {self.rate_eur.currency_id.id} Date {self.rate_eur.name} Company {self.rate_eur.company_id.id}")
        
        # Verify rate exists via search
        found_rate = self.Rate.search([
            ("currency_id", "=", self.currency_eur.id),
            ("company_id", "=", self.company.id),
            ("name", "=", self.today)
        ])
        _logger.warning(f"SETUP CHECK: Found Rate EUR: {found_rate}")

        self.partner = self.env["res.partner"].create({
            "name": "Partner EUR",
            "property_payment_term_id": self.env.ref("account.account_payment_term_immediate").id,
        })
        
        self.product = self.env["product.product"].create({
            "name": "Service EUR",
            "type": "service",
            "list_price": 100.0,
        })
        
        # Create a journal for EUR if needed, or use Bank and force currency
        self.bank_journal = self.env["account.journal"].search([('type', '=', 'bank'), ('company_id', '=', self.company.id)], limit=1)
        if not self.bank_journal:
             self.bank_journal = self.env["account.journal"].create({
                "name": "Bank",
                "type": "bank",
                "code": "BNK",
                "currency_id": self.currency_vef.id,
            })

    def test_payment_eur_assignment(self):
        """
        Test that a payment in EUR gets the correct rates assigned.
        Structure:
        1. Company Main: VEF
        2. Secondary: USD
        3. Payment: EUR
        """
        _logger.warning("TEST START: test_payment_eur_assignment")
        
        # Create Invoice in EUR
        move = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "currency_id": self.currency_eur.id,
            "invoice_date": self.today,
            "invoice_date_display": self.today,
            "date": self.today,
            "invoice_line_ids": [(0, 0, {
                "product_id": self.product.id,
                "price_unit": 100.0,
            })],
        })
        move.action_post()
        
        _logger.warning("Creating Payment...")
        payment_method_manual = self.env.ref("account.account_payment_method_manual_in")
        
        payment = self.env["account.payment"].with_company(self.company).create({
            "amount": 100.0,
            "date": self.today,
            "currency_id": self.currency_eur.id,
            "payment_type": "inbound",
            "partner_type": "customer",
            "partner_id": self.partner.id,
            "journal_id": self.bank_journal.id,
            "payment_method_id": payment_method_manual.id,
        })
        
        payment._compute_other_rate()
        
        expected_other_rate = 45.0
        expected_other_inverse_rate = 1.0 / 45.0

        self.assertEqual(payment.foreign_rate, 0.0, "Foreign Rate should be 0.0 for Third Currency (EUR)")

        _logger.info(f"Payment EUR Rates: Other Rate={payment.other_rate}, Other Inverse Rate={payment.other_rate_inverse}")
        
        self.assertAlmostEqual(payment.other_rate, expected_other_rate, places=2, msg="Other Rate should be the inverse company rate (VEF per EUR)")
        self.assertAlmostEqual(payment.other_rate_inverse, expected_other_inverse_rate, places=5, msg="Other Inverse Rate should be the company rate (EUR per VEF)")
        
