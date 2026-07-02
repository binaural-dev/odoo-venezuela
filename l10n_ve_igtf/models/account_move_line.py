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