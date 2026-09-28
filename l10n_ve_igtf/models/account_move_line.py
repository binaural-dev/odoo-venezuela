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
        """The core doesn't recognize an "advance cross" move
        (`is_advance_move=True`) as a real payment, so it would rate the
        reconciliation at the invoice date's rate instead of the cross's
        real one. Forcing `forced_rate_from_register_payment` -- the same
        hook core's own payment-register wizard uses -- makes core's
        unmodified `get_odoo_rate()` pick it up immediately (first line of
        that closure), without copying the rest of the method.
        """
        aml = aml_values['aml']
        other_aml = (other_aml_values or {}).get('aml')
        if (
            other_aml
            and other_aml.move_id.is_advance_move
            and not (aml.move_id.origin_payment_id or aml.move_id.statement_line_id or aml.move_id.is_advance_move)
            and not self.env.context.get('forced_rate_from_register_payment')
        ):
            balance = other_aml._get_reconciliation_aml_field_value('balance', shadowed_aml_values)
            amount_currency = other_aml._get_reconciliation_aml_field_value('amount_currency', shadowed_aml_values)
            if not other_aml.company_currency_id.is_zero(balance) and not counterpart_currency.is_zero(amount_currency):
                self = self.with_context(forced_rate_from_register_payment=abs(amount_currency / balance))
        return super()._prepare_move_line_residual_amounts(
            aml_values, counterpart_currency,
            shadowed_aml_values=shadowed_aml_values,
            other_aml_values=other_aml_values,
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