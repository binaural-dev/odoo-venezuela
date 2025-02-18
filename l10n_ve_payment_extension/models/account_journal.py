from odoo import api, fields, models


class AccountJournal(models.Model):
    _inherit = "account.journal"

    def _get_default_account_domain(self):
        return """[
            ('deprecated', '=', False),
            ('company_id', '=', company_id),
            ('account_type', 'in', ('asset_cash', 'liability_credit_card','asset_current','liability_current') if type == 'bank'
                                   else ('asset_cash',) if type == 'cash'
                                   else ('income', 'income_other','expense') if type == 'sale'
                                   else ('expense', 'expense_depreciation', 'expense_direct_cost') if type == 'purchase'
                                   else ('asset_receivable', 'asset_cash', 'asset_current', 'asset_non_current',
                                         'asset_prepayments', 'asset_fixed', 'liability_payable',
                                         'liability_credit_card', 'liability_current', 'liability_non_current',
                                         'equity', 'equity_unaffected', 'income', 'income_other', 'expense',
                                         'expense_depreciation', 'expense_direct_cost', 'off_balance'))
        ]"""
