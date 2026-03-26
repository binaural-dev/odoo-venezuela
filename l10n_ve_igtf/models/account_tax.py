from odoo import models, api, _
from odoo.tools.misc import formatLang
from odoo.tools.float_utils import float_round, float_is_zero


import logging

_logger = logging.getLogger(__name__)


class AccountTax(models.Model):
    _inherit = "account.tax"

    def _get_tax_totals_summary(
        self, base_lines, currency, company, cash_rounding=None
    ):
        """
        Extends the tax totals summary to include IGTF (Large Financial Transactions Tax) calculations.

        This method overrides the standard Odoo tax summary logic to calculate and append 
        IGTF-related data. It dynamically detects whether the source is an Invoice 
        (account.move) or a Sales Order (sale.order) and computes the tax amounts in 
        both local and foreign currencies based on the company's configuration and 
        the inverse exchange rate.

        :param list base_lines: List of dictionaries containing base lines for tax calculation.
        :param recordset currency: The document's primary currency (res.currency).
        :param recordset company: The company recordset used to retrieve IGTF settings.
        :param float cash_rounding: Optional parameter for cash rounding logic.

        :return: dict: Updated tax totals dictionary including an 'igtf' key with:
                    - apply_igtf (bool): Whether the tax is applicable.
                    - igtf_amount (float): Calculated tax amount in local currency.
                    - foreign_igtf_amount (float): Calculated tax amount in foreign currency.
                    - is_igtf_suggested (bool): Whether the amount is an informative suggestion.
        """
        
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
            if invoice.currency_id.id != invoice.company_id.currency_id.id:
                base_igtf = invoice.foreign_bi_igtf
                foreign_base_igtf = invoice.bi_igtf
            else:
                base_igtf = invoice.bi_igtf
                foreign_base_igtf = invoice.foreign_bi_igtf

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
        

        res["amount_total_igtf"] = res["base_amount_currency"] + igtf_amount
        
        res["formatted_amount_total_igtf"] = formatLang(
            self.env, res["amount_total_igtf"], currency_obj=currency
        )
        res["foreign_amount_total_igtf"] = res["base_amount_currency"] + foreign_igtf_amount
        
        res["formatted_foreign_amount_total_igtf"] = formatLang(
            self.env, res["foreign_amount_total_igtf"], currency_obj=foreign_currency
        )
        res["igtf"]["is_igtf_suggested"] = is_igtf_suggested

        return res