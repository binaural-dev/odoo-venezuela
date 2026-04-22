import datetime
from unittest.mock import patch
from odoo.tests import TransactionCase, tagged
from odoo import fields, Command

@tagged("post_install", "-at_install", "l10n_ve_invoice")
class TestCancelVisibility(TransactionCase):

    def setUp(self):
        super(TestCancelVisibility, self).setUp()
        self.company = self.env.user.company_id
        # Ensure 'taxpayer_type' exists, otherwise likely added by this module
        # Set default to ordinary
        if 'taxpayer_type' in self.company._fields:
            self.company.taxpayer_type = 'ordinary'
        
        # Setup Accounts with modern 'account_type' field (v15+)
        self.account_receivable = self.env['account.account'].create({
            'name': 'Receivable',
            'code': '1111111',
            'account_type': 'asset_receivable',
            'reconcile': True,
        })
        self.account_payable = self.env['account.account'].create({
            'name': 'Payable',
            'code': '2222222',
            'account_type': 'liability_payable',
            'reconcile': True,
        })
        self.account_revenue = self.env['account.account'].create({
            'name': 'Revenue',
            'code': '4444444',
            'account_type': 'income',
        })
        self.account_expense = self.env['account.account'].create({
            'name': 'Expense',
            'code': '5555555',
            'account_type': 'expense',
        })

        self.partner = self.env['res.partner'].create({
            'name': 'Test Partner',
            'property_account_receivable_id': self.account_receivable.id,
            'property_account_payable_id': self.account_payable.id,
        })
        
        self.currency = self.env.ref('base.VEF')
        self.foreign_currency = self.env.ref('base.USD')
        self.company.currency_id = self.currency
        self.company.foreign_currency_id = self.foreign_currency

        self.journal_sale = self.env['account.journal'].create({
            'name': 'Sale Journal',
            'type': 'sale',
            'code': 'SALE1',
            'default_account_id': self.account_revenue.id,
        })
        self.journal_purchase = self.env['account.journal'].create({
            'name': 'Purchase Journal',
            'type': 'purchase',
            'code': 'PURCH1',
            'default_account_id': self.account_expense.id,
        })
        
        self.product = self.env['product.product'].create({
            'name': 'Product Test',
            'type': 'service',
            'property_account_income_id': self.account_revenue.id,
            'property_account_expense_id': self.account_expense.id,
        })
        
    def _create_invoice(self, move_type, date_str):
        invoice = self.env['account.move'].create({
            'move_type': move_type,
            'partner_id': self.partner.id,
            'invoice_date': date_str,
            'invoice_date_display': date_str,
            'date': date_str,
            'journal_id': self.journal_sale.id if 'out' in move_type else self.journal_purchase.id,
            'invoice_line_ids': [Command.create({
                'name': 'product',
                'product_id': self.product.id, # Ensure product is used to trigger onchange/defaults if any
                'price_unit': 100.0,
            })],
        })
        return invoice

    def test_ordinary_in_period(self):
        """Ordinary: Invoice inside period -> Cancel available (entry_in_period=True)"""
        if 'taxpayer_type' not in self.company._fields:
            return
            
        self.company.taxpayer_type = 'ordinary'
        
        # Today: 2025-10-30
        # Invoice: 2025-10-29
        # Expect: True
        
        with patch('odoo.addons.l10n_ve_invoice.models.account_move.date') as mock_date:
            mock_date.today.return_value = datetime.date(2025, 10, 30)
            mock_date.side_effect = lambda *args, **kw: datetime.date(*args, **kw)

            inv = self._create_invoice('out_invoice', '2025-10-29')
            # Trigger compute
            inv._compute_entry_in_period()
            # Currently fails because code excludes 'out_invoice' unless debit_origin_id
            self.assertTrue(inv.entry_in_period, "Ordinary: Standard Invoice in period should be True")
            
    def test_ordinary_out_period(self):
        """Ordinary: Invoice outside period -> Cancel unavailable (entry_in_period=False)"""
        if 'taxpayer_type' not in self.company._fields:
            return
        self.company.taxpayer_type = 'ordinary'
        
        # Today: 2025-11-01
        # Invoice: 2025-10-29
        # Expect: False
        
        with patch('odoo.addons.l10n_ve_invoice.models.account_move.date') as mock_date:
            mock_date.today.return_value = datetime.date(2025, 11, 1)
            mock_date.side_effect = lambda *args, **kw: datetime.date(*args, **kw)

            inv = self._create_invoice('out_invoice', '2025-10-29')
            inv._compute_entry_in_period()
            self.assertFalse(inv.entry_in_period, "Ordinary: Invoice last month should be False")

    def test_special_in_period_first_half(self):
        """Special: Invoice 10th, Today 14th -> True"""
        if 'taxpayer_type' not in self.company._fields:
            return
        self.company.taxpayer_type = 'special'
        
        with patch('odoo.addons.l10n_ve_invoice.models.account_move.date') as mock_date:
            mock_date.today.return_value = datetime.date(2025, 10, 14)
            mock_date.side_effect = lambda *args, **kw: datetime.date(*args, **kw)

            inv = self._create_invoice('out_invoice', '2025-10-10')
            inv._compute_entry_in_period()
            self.assertTrue(inv.entry_in_period, "Special: Same fortnight (1st) should be True")

    def test_special_out_period_cross_half(self):
        """Special: Invoice 10th, Today 16th -> False"""
        if 'taxpayer_type' not in self.company._fields:
            return
        self.company.taxpayer_type = 'special'
        
        with patch('odoo.addons.l10n_ve_invoice.models.account_move.date') as mock_date:
            mock_date.today.return_value = datetime.date(2025, 10, 16)
            mock_date.side_effect = lambda *args, **kw: datetime.date(*args, **kw)

            inv = self._create_invoice('out_invoice', '2025-10-10')
            inv._compute_entry_in_period()
            self.assertFalse(inv.entry_in_period, "Special: Cross fortnight should be False")
    
    def test_vendor_bill_always_true(self):
        """Vendor Bill: Should always be True"""
        self.company.taxpayer_type = 'ordinary'
        
        with patch('odoo.addons.l10n_ve_invoice.models.account_move.date') as mock_date:
            mock_date.today.return_value = datetime.date(2025, 12, 1)
            mock_date.side_effect = lambda *args, **kw: datetime.date(*args, **kw)

            inv = self._create_invoice('in_invoice', '2025-01-01')
            inv._compute_entry_in_period()
            
            self.assertTrue(inv.entry_in_period, "Vendor Bill should always be True")
