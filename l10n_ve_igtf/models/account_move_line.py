from odoo import api, fields, models, _
from odoo.exceptions import UserError

import logging

_logger = logging.getLogger(__name__)
class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    payment_id_advance = fields.Many2one(
        "account.payment",
        string="Payment Advance"
    )

    @api.model
    def _prepare_move_line_residual_amounts(self, aml_values, counterpart_currency, shadowed_aml_values=None, other_aml_values=None):
        """Full override: `is_payment`/`get_odoo_rate`/`get_accounting_rate`
        are LOCAL functions inside the core method, so a single line can't
        be patched in isolation. Only change: `is_payment()` also treats an
        "advance cross" move (`is_advance_move=True`) as a real payment,
        so reconciliation uses its true rate instead of the invoice date's.

        MAINTENANCE WARNING: exact copy of core's
        `_prepare_move_line_residual_amounts` (Odoo 19.0,
        `account_move_line.py:2112-2188`) plus one line below. Re-diff
        against core on every Odoo upgrade.
        """

        def is_payment(aml):
            # Only change vs. core: also recognize `is_advance_move`.
            return aml.move_id.origin_payment_id or aml.move_id.statement_line_id or aml.move_id.is_advance_move

        def get_odoo_rate(aml, other_aml, currency):
            if forced_rate := self.env.context.get('forced_rate_from_register_payment'):
                return forced_rate
            if other_aml and not is_payment(aml) and is_payment(other_aml):
                return get_accounting_rate(other_aml, currency)
            if aml.move_id.is_invoice(include_receipts=True):
                exchange_rate_date = aml.move_id.invoice_date
            else:
                exchange_rate_date = aml._get_reconciliation_aml_field_value('date', shadowed_aml_values)
            return currency._get_conversion_rate(aml.company_currency_id, currency, aml.company_id, exchange_rate_date)

        def get_accounting_rate(aml, currency):
            balance = aml._get_reconciliation_aml_field_value('balance', shadowed_aml_values)
            amount_currency = aml._get_reconciliation_aml_field_value('amount_currency', shadowed_aml_values)
            if not aml.company_currency_id.is_zero(balance) and not currency.is_zero(amount_currency):
                return abs(amount_currency / balance)

        aml = aml_values['aml']
        other_aml = (other_aml_values or {}).get('aml')
        remaining_amount_curr = aml_values['amount_residual_currency']
        remaining_amount = aml_values['amount_residual']
        company_currency = aml.company_currency_id
        currency = aml._get_reconciliation_aml_field_value('currency_id', shadowed_aml_values)
        account = aml._get_reconciliation_aml_field_value('account_id', shadowed_aml_values)
        has_zero_residual = company_currency.is_zero(remaining_amount)
        has_zero_residual_currency = currency.is_zero(remaining_amount_curr)
        is_rec_pay_account = account.account_type in ('asset_receivable', 'liability_payable')

        available_residual_per_currency = {}

        if not has_zero_residual:
            available_residual_per_currency[company_currency] = {
                'residual': remaining_amount,
                'rate': 1,
            }
        if currency != company_currency and not has_zero_residual_currency:
            available_residual_per_currency[currency] = {
                'residual': remaining_amount_curr,
                'rate': get_accounting_rate(aml, currency),
            }

        if currency == company_currency \
            and is_rec_pay_account \
            and not has_zero_residual \
            and counterpart_currency != company_currency:
            rate = get_odoo_rate(aml, other_aml, counterpart_currency)
            residual_in_foreign_curr = counterpart_currency.round(remaining_amount * rate)
            if not counterpart_currency.is_zero(residual_in_foreign_curr):
                available_residual_per_currency[counterpart_currency] = {
                    'residual': residual_in_foreign_curr,
                    'rate': rate,
                }
        elif currency == counterpart_currency \
            and currency != company_currency \
            and not has_zero_residual_currency:
            available_residual_per_currency[counterpart_currency] = {
                'residual': remaining_amount_curr,
                'rate': get_accounting_rate(aml, currency),
            }
        return available_residual_per_currency


    def action_register_payment(self):
        """ 
        # 1. Validate Unique Partner
        # 2. Validate Unique Currency
        # 3. Optional: Validate Unique Company (Best practice for Multi-company)
        # If all validations pass, call the original Odoo function"""

        partners = self.mapped('partner_id')
        if len(partners) > 1:
            raise UserError(_("You cannot register payments for different partners at the same time. "
                              "Please select invoices belonging to a single contact."))

       
        currencies = self.mapped('move_id.currency_id')
        if len(currencies) > 1:
            raise UserError(_("You cannot register payments with multiple currencies. "
                              "All selected invoices must have the same currency."))
        
        
        companies = self.mapped('move_id.company_id')
        if len(companies) > 1:
            raise UserError(_("You cannot register payments for different companies at the same time."))

        
        return super(AccountMoveLine, self).action_register_payment()