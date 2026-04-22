from odoo import api, fields, models, _
from odoo.tools import float_round, float_is_zero
from odoo.exceptions import UserError

import logging

_logger = logging.getLogger(__name__)
class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    payment_id_advance = fields.Many2one(
        "account.payment",
        string="Payment Advance"
    )

    @api.onchange('amount_currency', 'currency_id')
    def _inverse_amount_currency(self):
        """
        Updates the 'balance' (company currency amount) whenever the 'amount_currency' 
        or 'currency_id' changes, ensuring a symmetric rounding.

        This method addresses the common floating-point discrepancy where a balance 
        converted to foreign currency and then back to company currency results in 
        a small difference (e.g., 0.01). 

        The logic performs a "Symmetry Test":
        1. It calculates the initial balance using the current exchange rate.
        2. It simulates a back-conversion to the foreign currency.
        3. If the back-conversion doesn't match the original 'amount_currency' due to 
        rounding noise, it applies a micro-adjustment to the 'balance' in the 
        company currency (VES) to force a perfect match.

        :return: None
        """
        for line in self:
            if line.currency_id == line.company_id.currency_id and line.balance != line.amount_currency:
                line.balance = line.amount_currency
                
            elif (
                line.currency_id != line.company_id.currency_id
                and not line.move_id.is_invoice(True)
                and not self.env.is_protected(self._fields['balance'], line)
            ):
                rate = line.currency_rate
                if not rate:
                    continue
                    
                raw_balance = line.amount_currency / rate
                
                rounded_balance = line.company_id.currency_id.round(raw_balance)
                
                back_to_foreign = rounded_balance * rate
                diff_foreign = line.amount_currency - back_to_foreign
                
                if not float_is_zero(diff_foreign, precision_rounding=line.currency_id.rounding):
                    adjustment = float_round(diff_foreign / rate, precision_rounding=line.company_id.currency_id.rounding)
                    line.balance = rounded_balance + adjustment
                else:
                    line.balance = rounded_balance


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