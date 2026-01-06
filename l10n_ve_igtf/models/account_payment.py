from odoo import api, models, fields, _, Command
from odoo.exceptions import UserError
from odoo.tools import float_is_zero , float_compare

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
       
        for rec in self:
            vals = super(AccountPaymentIgtf, self)._prepare_move_line_default_vals(
                write_off_line_vals,
                force_balance
            )
            if rec.payment_from_wizard:
                if rec.igtf_percentage and rec.igtf_amount:
                    rec._create_igtf_moves_in_payments(vals, write_off_line_vals)

            return vals

    def calculate_igtf_for_payment(self, invoice, payment_amount, igtf_percentage=False):
        
        currency = invoice.currency_id
        precision = currency.rounding
        
        principal_debt = invoice.amount_residual if invoice.company_currency_id != self.env.ref("base.VEF") else invoice.foreign_amount_residual

        principal_amount = min(payment_amount, principal_debt)
        

        igtf_unrounded = principal_amount * (self.env.company.igtf_percentage / 100)

        igtf_top = invoice.igtf_top_aply

        alter_bi_igtf = invoice.alter_bi_igtf

        igtf= igtf_unrounded

        invoice_residual = invoice.amount_residual if self.company_currency_id != self.env.ref("base.VEF") else invoice.foreign_amount_residual
    
        if not float_is_zero(igtf, precision_rounding=precision) and igtf_top == invoice_residual:
            
            return 0.0
        
        if float_compare(igtf_top, 0.0, precision_rounding=precision) >= 0.0 and float_compare(igtf, igtf_top, precision_rounding=precision) > 0.0:
            
            return 0.0
        

        residual_igtf = igtf_top - alter_bi_igtf

        
        if igtf > residual_igtf and  not float_is_zero(residual_igtf, precision_rounding=precision):
            igtf = residual_igtf
     

        return igtf
    
    def _create_igtf_moves_in_payments(self, vals, write_off_line_vals = False):
        
        igtf_account = (
            self.env.company.customer_account_igtf_id.id
            if self.partner_type == "customer"
            else self.env.company.supplier_account_igtf_id.id
        )

        if self._context.get("from_pos", False):
            return

        for payment in self:
            
            if payment.igtf_amount:
                if payment.payment_type == "inbound":
                    vals_igtf = [x for x in vals if x["account_id"] == igtf_account]

                    if not vals_igtf:
                        payment._prepare_inbound_move_line_igtf_vals(vals, write_off_line_vals)

                if payment.payment_type == "outbound":
                    vals_igtf = [x for x in vals if x["account_id"] == igtf_account]
                    if not vals_igtf:
                        payment._prepare_outbound_move_line_igtf_vals(vals,write_off_line_vals)

    def _create_inbound_move_line_igtf_vals(self, vals):
        
        for rec in self:
            igtf_account = (
                self.env.company.customer_account_igtf_id.id
                if rec.partner_type == "customer"
                else self.env.company.supplier_account_igtf_id.id
            )
            igtf_amount = rec.igtf_amount
            account_id = igtf_account if rec.igtf_percentage else None
            currency = self.currency_id 
            precision = currency.rounding
            if float_compare(igtf_amount, 0.0, precision_rounding=precision) > 0.0:
                
                vals.append(
                    {
                        "name": "IGTF",
                        "currency_id": rec.currency_id.id,
                        "amount_currency": -igtf_amount,
                        "account_id": account_id,
                        "partner_id": rec.partner_id.id,
                    }
                )
        return vals

    def _create_outbound_move_line_igtf_vals(self, vals):
        
        for rec in self:
            igtf_account = (
                self.env.company.customer_account_igtf_id.id
                if rec.partner_type == "customer"
                else self.env.company.supplier_account_igtf_id.id
            )
            igtf_amount = rec.igtf_amount
            account_id = igtf_account if rec.igtf_percentage else None
            currency = self.currency_id 
            precision = currency.rounding
            if float_compare(igtf_amount, 0.0, precision_rounding=precision) > 0.0:

                vals.append(
                    {
                        "name": "IGTF",
                        "currency_id": rec.currency_id.id,
                        "amount_currency": igtf_amount,
                        "account_id": account_id,
                        "partner_id": rec.partner_id.id,
                    }
                )

        return vals

    def _prepare_inbound_move_line_igtf_vals(self, vals, write_off_line_vals = False):
    
        for rec in self:
            lines = [line for line in vals]
            if rec.payment_type == "inbound":
                currency = rec.currency_id
                credit_line_unrounded = lines[1]["amount_currency"] - rec.igtf_amount
                credit_line = credit_line_unrounded
                credit_amount = -credit_line
                if self.env.company.currency_id.id == self.env.ref("base.VEF").id:
                    
                    credit_amount = -(credit_line / rec.foreign_inverse_rate)
                currency = rec.currency_id 
                precision = currency.rounding
                if float_compare(rec.igtf_amount, 0.0, precision_rounding=precision) > 0.0:
                    vals[1].update({"amount_currency": credit_line, "credit": credit_amount})
                rec._create_inbound_move_line_igtf_vals(vals)
                
    def _prepare_outbound_move_line_igtf_vals(self, vals,write_off_line_vals =False):
        
        for rec in self:
            lines = [line for line in vals]
            if rec.payment_type == "outbound":

                currency = rec.currency_id
                debit_line_unrounded = lines[1]["amount_currency"] - rec.igtf_amount
                debit_line = debit_line_unrounded
                debit_amount = debit_line
                if self.env.company.currency_id.id == self.env.ref("base.VEF").id:
                    
                    debit_amount = debit_line / rec.foreign_inverse_rate
                currency = rec.currency_id 
                precision = currency.rounding
                if float_compare(rec.igtf_amount, 0.0, precision_rounding=precision) > 0.0:
                    vals[1].update({"amount_currency": debit_line, "debit": debit_amount})

                rec._create_outbound_move_line_igtf_vals(vals)
            
    @api.depends('journal_id')
    def _compute_is_igtf_journal(self):
        for record in self:
            if record.journal_id.currency_id and record.journal_id.currency_id == self.env.ref("base.USD"):
                record.is_igtf_on_foreign_exchange = True
            else:
                record.is_igtf_on_foreign_exchange = False


    
    