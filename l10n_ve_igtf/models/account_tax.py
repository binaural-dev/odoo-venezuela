from odoo import models, api, _
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

        for base_line in base_lines:
            type_model = base_line["record"]._name
            if base_line["record"]._name == "account.move.line":
                invoice = base_line["record"].move_id
            if base_line["record"]._name == "sale.order.line":
                order = base_line["record"].order_id


        apply_igtf = False
        igtf_show = False
        base_igtf = 0
        foreign_base_igtf = 0

        foreign_currency = invoice.company_id.currency_id
        
        float_igtf_percentage = self.env.company.igtf_percentage
        show_igtf_suggested_account_move =  self.env.company.show_igtf_suggested_account_move

        igtf_percentage = (float_igtf_percentage or 0) / 100
        
        if invoice.bi_igtf > 0.0:
            apply_igtf = True
            if invoice.currency_id.id != invoice.company_id.currency_id.id:
                base_igtf = invoice.foreign_bi_igtf
                foreign_base_igtf = invoice.bi_igtf
            else:
                base_igtf = invoice.bi_igtf
                foreign_base_igtf = invoice.foreign_bi_igtf
        else:
            if invoice.move_type == "out_invoice" and invoice.payment_state == "not_paid":
                igtf_show = True

            if invoice.currency_id.id != invoice.company_id.currency_id.id:
                base_igtf = invoice.amount_total
                foreign_base_igtf = invoice.amount_total_signed 
            else:

                if invoice.invoice_date_due and invoice.invoice_date and invoice.invoice_date_due > invoice.invoice_date:
                    base_igtf = invoice.amount_total_signed 
                    foreign_base_igtf = invoice.amount_total
                    igtf_show = True
                else:
                    igtf_show = False

        base_igtf_free = 0.0
        foreign_base_igtf_free = 0.0
        if invoice.move_type == "out_invoice":
            if invoice.currency_id.id != invoice.company_id.currency_id.id:
                base_igtf_free = invoice.amount_total
                foreign_base_igtf_free = invoice.amount_total_signed 
            else:
                if invoice.invoice_date_due and invoice.invoice_date and invoice.invoice_date_due > invoice.invoice_date:
                    base_igtf_free = invoice.amount_total_signed 
                    foreign_base_igtf_free = invoice.amount_total
                else:
                    base_igtf_free = 0.0 
                    foreign_base_igtf_free = 0.0


        igtf_base_amount = base_igtf 
        igtf_foreign_base_amount = foreign_base_igtf 

        igtf_amount = igtf_base_amount * igtf_percentage 
        foreign_igtf_base_amount = igtf_foreign_base_amount * igtf_percentage 


        igtf_base_amount_free = base_igtf_free 
        igtf_foreign_base_amount_free = foreign_base_igtf_free 

        igtf_amount_free = igtf_base_amount_free * igtf_percentage 
        foreign_igtf_base_amount_free = igtf_foreign_base_amount_free * igtf_percentage 
        

        res["igtf"] = {}
        res["igtf"]["apply_igtf"] = apply_igtf
        res["igtf"]["igtf_show"] = igtf_show
        res["igtf"]["name"] = f"{float_igtf_percentage} %"

        res["igtf"]["igtf_base_amount"] = igtf_base_amount 
        res["igtf"]["formatted_igtf_base_amount"] = formatLang( 
            self.env, igtf_base_amount, currency_obj=currency
        )
        res["igtf"]["foreign_igtf_base_amount"] = igtf_foreign_base_amount 
        res["igtf"]["formatted_foreign_igtf_base_amount"] = formatLang( 
            self.env, igtf_foreign_base_amount, currency_obj=foreign_currency
        )

        res["igtf"]["igtf_amount"] = igtf_amount 
        res["igtf"]["formatted_igtf_amount"] = formatLang( 
             self.env, igtf_amount, currency_obj=currency
         )

        res["igtf"]["foreign_igtf_amount"] = foreign_igtf_base_amount 
        res["igtf"]["formatted_foreign_igtf_amount"] = formatLang( 
            self.env, foreign_igtf_base_amount, currency_obj=foreign_currency
        )

        res["amount_total_igtf"] = invoice.amount_total + igtf_amount
        res["formatted_amount_total_igtf"] = formatLang(
            self.env, res["amount_total_igtf"], currency_obj=currency
        )

        res["foreign_amount_total_igtf"] = invoice.amount_total_signed + foreign_igtf_base_amount
        res["formatted_foreign_amount_total_igtf"] = formatLang(
            self.env, res["foreign_amount_total_igtf"], currency_obj=foreign_currency
        )

        # Free-Form Values
        if invoice.move_type == "out_invoice": 
            res["igtf_free_form"] = {}
            res["igtf_free_form"]["show_igtf_suggested_account_move"] = show_igtf_suggested_account_move
            res["igtf_free_form"]["name"] = f"{float_igtf_percentage} %"

            res["igtf_free_form"]["igtf_base_amount_free"] = igtf_base_amount_free 
            res["igtf_free_form"]["formatted_igtf_base_amount_free"] = formatLang( 
                self.env, igtf_base_amount_free, currency_obj=currency
            )
            res["igtf_free_form"]["foreign_igtf_base_amount_free"] = igtf_foreign_base_amount_free 
            res["igtf_free_form"]["formatted_foreign_igtf_base_amount_free"] = formatLang( 
                self.env, igtf_foreign_base_amount_free, currency_obj=foreign_currency
            )

            res["igtf_free_form"]["igtf_amount_free"] = igtf_amount_free 
            res["igtf_free_form"]["formatted_igtf_amount_free"] = formatLang( 
                self.env, igtf_amount_free, currency_obj=currency
            )

            res["igtf_free_form"]["foreign_igtf_amount_free"] = foreign_igtf_base_amount_free 
            res["igtf_free_form"]["formatted_foreign_igtf_amount_free"] = formatLang( 
                self.env, foreign_igtf_base_amount_free, currency_obj=foreign_currency
            )

            res["igtf_free_form"]["amount_total_igtf_free"] = invoice.amount_total + igtf_amount_free
            res["igtf_free_form"]["formatted_amount_total_igtf_free"] = formatLang(
                self.env, res["igtf_free_form"]["amount_total_igtf_free"], currency_obj=currency
            )

            res["igtf_free_form"]["foreign_amount_total_igtf_free"] = invoice.amount_total_signed + foreign_igtf_base_amount_free
            res["igtf_free_form"]["formatted_foreign_amount_total_igtf_free"] = formatLang(
                self.env, res["igtf_free_form"]["foreign_amount_total_igtf_free"], currency_obj=foreign_currency
            )

        

        return res