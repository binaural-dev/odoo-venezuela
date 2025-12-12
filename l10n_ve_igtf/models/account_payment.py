from odoo import api, models, fields, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class AccountPaymentIgtf(models.Model):
    _inherit = "account.payment"

    is_igtf_on_foreign_exchange = fields.Boolean(
        string="IGTF on Foreign Exchange?",
        help="IGTF on Foreign Exchange",
        compute="_compute_is_igtf",
        store=True,
    )

    igtf_percentage = fields.Float(
        string="IGTF Percentage",
        compute="_compute_igtf_percentage",
        help="IGTF Percentage",
        store=True,
    )

    igtf_amount = fields.Float(
        string="IGTF Amount",
        help="IGTF Amount",
    )

    payment_from_wizard = fields.Boolean()
    amount_residual_from_payment = fields.Float()

    @api.depends("partner_id")
    def _compute_igtf_percentage(self):
        for payment in self:
            payment.igtf_percentage = payment.env.company.igtf_percentage


    @api.depends("journal_id")
    def _compute_is_igtf(self):
        for payment in self:
            payment.is_igtf_on_foreign_exchange = False
            if payment.journal_id.is_igtf:
                payment.is_igtf_on_foreign_exchange = True

   
                   
    def _prepare_move_line_default_vals(self, write_off_line_vals=None, force_balance=None):
       
        vals = super(AccountPaymentIgtf, self)._prepare_move_line_default_vals(
            write_off_line_vals,
            force_balance
        )
        if self.payment_from_wizard:
            if self.igtf_percentage and self.journal_id.is_igtf:
                self._create_igtf_moves_in_payments(vals, write_off_line_vals)

        return vals

    def calculate_igtf_for_payment(self, invoice, payment_amount, igtf_percentage=False):
       
        currency = self.env.company.currency_id
        
        principal_debt = invoice.amount_residual
        principal_amount = min(payment_amount, principal_debt)
        
        igtf_unrounded = principal_amount * (self.env.company.igtf_percentage / 100)
        igtf_top = currency.round(invoice.igtf_top_aply) 
        igtf= currency.round(igtf_unrounded)
        if igtf > 0 and igtf_top == invoice.amount_residual:
            
            return 0.0
        if igtf > igtf_top and igtf_top >= 0.0:
            
            return 0.0
        

        return max(igtf, 0.0)
    
    def _create_igtf_moves_in_payments(self, vals, write_off_line_vals = False):
        
        igtf_account = (
            self.env.company.customer_account_igtf_id.id
            if self.partner_type == "customer"
            else self.env.company.supplier_account_igtf_id.id
        )

        if self._context.get("from_pos", False):
            return

        for payment in self:
            move_id = (
                self.env.context.get("active_id", False)
            )
            
            if payment.is_igtf_on_foreign_exchange:
                #aplica solo para igtf
                if payment.payment_type == "inbound":
                    vals_igtf = [x for x in vals if x["account_id"] == igtf_account]

                    if not vals_igtf:
                        payment._prepare_inbound_move_line_igtf_vals(vals, write_off_line_vals)

                if payment.payment_type == "outbound":
                    vals_igtf = [x for x in vals if x["account_id"] == igtf_account]
                    if not vals_igtf:
                        payment._prepare_outbound_move_line_igtf_vals(vals,write_off_line_vals)

    def _create_inbound_move_line_igtf_vals(self, vals):
        
        igtf_account = (
            self.env.company.customer_account_igtf_id.id
            if self.partner_type == "customer"
            else self.env.company.supplier_account_igtf_id.id
        )
        igtf_amount = self.igtf_amount
        account_id = igtf_account if self.igtf_percentage else None
        if igtf_amount > 0.0:
            vals.append(
                {
                    "name": "IGTF",
                    "currency_id": self.currency_id.id,
                    "amount_currency": -igtf_amount,
                    "account_id": account_id,
                    "partner_id": self.partner_id.id,
                }
            )

        return vals

    def _create_outbound_move_line_igtf_vals(self, vals):
       
        igtf_account = (
            self.env.company.customer_account_igtf_id.id
            if self.partner_type == "customer"
            else self.env.company.supplier_account_igtf_id.id
        )
        igtf_amount = self.igtf_amount
        account_id = igtf_account if self.igtf_percentage else None

        if igtf_amount > 0.0:
            vals.append(
                {
                    "name": "IGTF",
                    "currency_id": self.currency_id.id,
                    "amount_currency": igtf_amount,
                    "account_id": account_id,
                    "partner_id": self.partner_id.id,
                }
            )

        return vals

    def _prepare_inbound_move_line_igtf_vals(self, vals, write_off_line_vals = False):
    

        lines = [line for line in vals]
        if self.payment_type == "inbound":
            currency = self.currency_id
            
            
            credit_line_unrounded = lines[1]["amount_currency"] + self.igtf_amount
           
            credit_line = currency.round(credit_line_unrounded)
            
            credit_amount = -credit_line

            if self.env.company.currency_id.id == self.env.ref("base.VEF").id:
                credit_amount = currency.round(-credit_line * self.foreign_rate)
            
            if self.igtf_amount > 0:
                vals[1].update({"amount_currency": credit_line, "credit": credit_amount})
           
            self._create_inbound_move_line_igtf_vals(vals)
                
    def _prepare_outbound_move_line_igtf_vals(self, vals,write_off_line_vals =False):
     
        lines = [line for line in vals]
        if self.payment_type == "outbound":
            currency = self.currency_id
            
            debit_line_unrounded = lines[1]["amount_currency"] - self.igtf_amount 
            
            debit_line = currency.round(debit_line_unrounded)
            

            debit_amount = debit_line
            if self.env.company.currency_id.id == self.env.ref("base.VEF").id:
                debit_amount = currency.round(debit_line * self.foreign_rate) 
                
            if self.igtf_amount > 0:
                vals[1].update({"amount_currency": debit_line, "debit": debit_amount})

            self._create_outbound_move_line_igtf_vals(vals)


    @api.depends('journal_id')
    def _compute_is_igtf_journal(self):
        for record in self:
            if record.journal_id.currency_id and record.journal_id.currency_id == self.env.ref("base.USD"):
                record.is_igtf_on_foreign_exchange = True
            else:
                record.is_igtf_on_foreign_exchange = False