from odoo import models, _
from odoo.tools.misc import formatLang
from odoo.tools.float_utils import float_round, float_is_zero
from odoo.exceptions import UserError


import logging

_logger = logging.getLogger(__name__)


class AccountTax(models.Model):
    _inherit = "account.tax"

    def _get_tax_totals_summary(
        self, base_lines, currency, company, cash_rounding=None
    ):
 
        
        res = super()._get_tax_totals_summary(base_lines, currency, company, cash_rounding)

        invoice = self.env["account.move"]
        order = False
        apply_igtf = False
        type_model = ""
        base_igtf = 0
        foreign_base_igtf = 0
        is_igtf_suggested = False
      
        for base_line in base_lines:
            type_model = base_line["record"]._name
            if base_line["record"]._name == "account.move.line":
                invoice = base_line["record"].move_id
            if base_line["record"]._name == "sale.order.line":
                order = base_line["record"].order_id

        foreign_currency = self.env.company.foreign_currency_id
        rate = 0

        if type_model == "account.move.line":
            rate = invoice.foreign_inverse_rate
        if type_model == "sale.order.line":
            rate = order.foreign_inverse_rate

        float_igtf_percentage = self.env.company.igtf_percentage

        igtf_percentage = (float_igtf_percentage or 0) / 100

        if (
            type_model == "account.move.line"
            and self.env.company.show_igtf_suggested_account_move
            and invoice.payment_state == "not_paid"
        ):
            is_igtf_suggested = True
            base_igtf = res.get("amount_total", 0)
            foreign_base_igtf = res.get("foreign_amount_total", 0)
        if (
            type_model == "sale.order.line"
            and self.env.company.show_igtf_suggested_sale_order
        ):
            is_igtf_suggested = True
            base_igtf = res.get("amount_total", 0)
            foreign_base_igtf = res.get("foreign_amount_total", 0)

        if invoice.bi_igtf:
               
            base_igtf = invoice.company_id.currency_id._convert(
            invoice.bi_igtf, 
            invoice.currency_id,
            self.company_id, 
            invoice.invoice_date
            )

        
            foreign_base_igtf =invoice.foreign_bi_igtf

        igtf_base_amount = base_igtf 
        igtf_foreign_base_amount = foreign_base_igtf 

        if (
            igtf_base_amount > 0
        ):
            
            apply_igtf = True

        foreign_igtf_base_amount = igtf_foreign_base_amount 

        igtf_amount = igtf_base_amount * igtf_percentage

        foreign_igtf_amount = igtf_foreign_base_amount * igtf_percentage
            

        res["igtf"] = {}
        res["igtf"]["apply_igtf"] = apply_igtf
        res["igtf"]["name"] = f"{float_igtf_percentage} %"

        res["igtf"]["igtf_base_amount"] = igtf_base_amount
        res["igtf"]["formatted_igtf_base_amount"] = formatLang(
            self.env, igtf_base_amount, currency_obj=currency
        )
        res["igtf"]["foreign_igtf_base_amount"] = foreign_igtf_base_amount
        res["igtf"]["formatted_foreign_igtf_base_amount"] = formatLang(
            self.env, foreign_igtf_base_amount, currency_obj=foreign_currency
        )

        res["igtf"]["igtf_amount"] = igtf_amount
        res["igtf"]["formatted_igtf_amount"] = formatLang(
            self.env, igtf_amount, currency_obj=currency
        )

        res["igtf"]["foreign_igtf_amount"] = foreign_igtf_amount
        res["igtf"]["formatted_foreign_igtf_amount"] = formatLang(
            self.env, foreign_igtf_amount, currency_obj=foreign_currency
        )
        

        res["amount_total_igtf"] = float_round(
            res["base_amount_currency"] + igtf_amount, precision_rounding=currency.rounding
        )
        res["formatted_amount_total_igtf"] = formatLang(
            self.env, res["amount_total_igtf"], currency_obj=currency
        )
        res["foreign_amount_total_igtf"] = float_round(
            res["base_amount_currency"] + foreign_igtf_amount,
            precision_rounding=foreign_currency.rounding,
        )
        res["formatted_foreign_amount_total_igtf"] = formatLang(
            self.env, res["foreign_amount_total_igtf"], currency_obj=foreign_currency
        )
        res["igtf"]["is_igtf_suggested"] = is_igtf_suggested

        return res

    def process_payments_to_igtf(self,invoice):
        invoice_payments_widget = invoice.invoice_payments_widget
        content = invoice_payments_widget.get("content", False) if invoice_payments_widget else False

        if not content:
            return 0

        payments_id = [
            payment['account_payment_id']
            for payment in content
            if 'account_payment_id' in payment
        ]

        payments = self.env["account.payment"].browse(payments_id)

        payments_igtf = payments.filtered(lambda p: p.is_igtf_on_foreign_exchange)

        amount_to_igtf = [
            payment["amount"]
            for payment in content
            if 'account_payment_id' in payment and payment['account_payment_id'] in payments_igtf.ids
        ]
        total_amount_to_igtf = sum(amount_to_igtf)  

        return total_amount_to_igtf

