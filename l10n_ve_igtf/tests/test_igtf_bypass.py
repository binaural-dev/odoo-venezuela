import logging
from odoo.tests import tagged, Form
from .test_common_purchase_book_igtf_usd_provider_formal import IGTFTestCommonPurchaseBook

_logger = logging.getLogger(__name__)

@tagged("igtf_bypass", "post_install", "-at_install")
class TestIGTFBypass(IGTFTestCommonPurchaseBook):

    def setUp(self):
        super().setUp()
        # Ensure no international journal exists from base setup
        existing = self.Journal.search([('is_purchase_international', '=', True), ('company_id', '=', self.company.id)])
        if existing:
            existing.write({'is_purchase_international': False})

    def test_bypass_igtf_on_invoice(self):
        """Test that IGTF fields are 0 when using an international purchase journal."""
        # Create an international purchase journal
        international_purchase_journal = self.Journal.create({
            'name': 'International Purchase Journal',
            'type': 'purchase',
            'code': 'INTPR',
            'company_id': self.company.id,
            'currency_id': self.currency_usd.id,
            'is_purchase_international': True,
        })

        invoice = self._create_invoice_usd(100.0)
        # Switch journal to international
        with Form(invoice) as inv_form:
            inv_form.journal_id = international_purchase_journal
            # Required field when is_purchase_international is True
            inv_form.declaration_unique_of_customs = "123456789"
        invoice = inv_form.save()
        
        invoice.action_post()

        self.assertEqual(invoice.bi_igtf, 0.0, "BI IGTF should be 0")
        self.assertEqual(invoice.foreign_bi_igtf, 0.0, "Foreign BI IGTF should be 0")

    def test_bypass_igtf_on_payment(self):
        """Test that payment does not generate IGTF moves when paying with international bank journal."""
        existing = self.Journal.search([('is_purchase_international', '=', True), ('company_id', '=', self.company.id)])
        if existing:
            existing.write({'is_purchase_international': False})

        # Create an international bank journal
        international_bank_journal = self.Journal.create({
            'name': 'International Bank Journal',
            'type': 'bank',
            'code': 'INTBK',
            'company_id': self.company.id,
            'currency_id': self.currency_usd.id,
            'is_igtf': True,  # Enabled IGTF but should be bypassed
            'is_purchase_international': True,
            'default_account_id': self.account_bank.id,
            'outbound_payment_method_line_ids': [(6, 0, self.pm_line_out_usd.ids)],
        })
        
        manual_out = self.env.ref("account.account_payment_method_manual_out") 
        pm_line_out_int = self.env["account.payment.method.line"].create({
            "name": "Manual Outbound INT",
            "payment_method_id": manual_out.id,
            "payment_type": "outbound",
            "payment_account_id": self.account_bank.id, 
            "journal_id": international_bank_journal.id,
        })
        international_bank_journal.write({
            'outbound_payment_method_line_ids': [(6, 0, pm_line_out_int.ids)],
        })

        invoice = self._create_invoice_usd(100.0)
        invoice.action_post()

        # Use Form to register payment to simulate real flow
        action_data = invoice.action_register_payment()
        with Form(self.env['account.payment.register'].with_context(action_data['context'])) as pay_form:
            pay_form.journal_id = international_bank_journal
            pay_form.currency_id = self.currency_usd
            # Amount should default to 100.0
        
        wizard = pay_form.save()
        action = wizard.action_create_payments()
        payment = self.env['account.payment'].browse(action['res_id'])
        
        # Verify no IGTF moves were created
        # Logic in account_payment.py prevents move lines creation.
        # But wizard might have calculated igtf_amount.
        # Let's check move lines count. Standard payment has 2 lines (Liquidity + AP).
        self.assertTrue(len(payment.move_id.line_ids) <= 2, "Should strictly have standard payment lines, no IGTF extras")
        
    def test_control_case(self):
        """Ensure standard behavior is preserved (IGTF is calculated) for local journals."""
        existing = self.Journal.search([('is_purchase_international', '=', True), ('company_id', '=', self.company.id)])
        if existing:
            existing.write({'is_purchase_international': False})

        invoice = self._create_invoice_usd(100.0)
        invoice.action_post()
        
        # Standard Bank Journal (IGTF enabled, NOT international)
        standard_bank_journal = self.bank_journal_usd
        
        action_data = invoice.action_register_payment()
        with Form(self.env['account.payment.register'].with_context(action_data['context'])) as pay_form:
            pay_form.journal_id = standard_bank_journal
            pay_form.currency_id = self.currency_usd
        
        wizard = pay_form.save()
        action = wizard.action_create_payments()
        payment = self.env['account.payment'].browse(action['res_id'])
        
        # Should have IGTF (3% of 100 = 3.0)
        self.assertAlmostEqual(payment.igtf_amount, 3.0, delta=0.01, msg="Control case: IGTF should be calculated")

    def test_bypass_wizard_igtf(self):
        """Test that IGTF flags are False in the payment wizard for international journals."""
        existing = self.Journal.search([('is_purchase_international', '=', True), ('company_id', '=', self.company.id)])
        if existing:
            existing.write({'is_purchase_international': False})

        # Create an international bank journal
        international_bank_journal = self.Journal.create({
            'name': 'International Bank Journal',
            'type': 'bank',
            'code': 'INTBK',
            'company_id': self.company.id,
            'currency_id': self.currency_usd.id,
            'is_igtf': True,  # Enabled IGTF but should be bypassed
            'is_purchase_international': True,
            'default_account_id': self.account_bank.id,
            'outbound_payment_method_line_ids': [(6, 0, self.pm_line_out_usd.ids)],
        })
        
        manual_out = self.env.ref("account.account_payment_method_manual_out") 
        pm_line_out_int = self.env["account.payment.method.line"].create({
            "name": "Manual Outbound INT",
            "payment_method_id": manual_out.id,
            "payment_type": "outbound",
            "payment_account_id": self.account_bank.id, 
            "journal_id": international_bank_journal.id,
        })
        international_bank_journal.write({
            'outbound_payment_method_line_ids': [(6, 0, pm_line_out_int.ids)],
        })

        invoice = self._create_invoice_usd(100.0)
        invoice.action_post()

        action_data = invoice.action_register_payment()
        with Form(self.env['account.payment.register'].with_context(action_data['context'])) as pay_form:
            # Select the international journal
            pay_form.journal_id = international_bank_journal
            pay_form.currency_id = self.currency_usd
            
        wizard = pay_form.save()
        
        # Assertions on the wizard state
        self.assertFalse(wizard.is_igtf, "IGTF should be False in wizard for international journal")
        self.assertFalse(wizard.is_igtf_on_foreign_exchange, "IGTF on Foreign Exchange should be False for international journal")
        self.assertEqual(wizard.igtf_amount, 0.0, "IGTF Amount should be 0 in wizard")
        self.assertEqual(wizard.igtf_to_show, 0.0, "IGTF to show should be 0 in wizard")
