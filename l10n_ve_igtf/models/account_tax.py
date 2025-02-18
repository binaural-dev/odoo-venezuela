from operator import is_
from odoo import api, models, _
from odoo.tools.misc import formatLang
from odoo.tools.float_utils import float_round, float_is_zero


import logging

_logger = logging.getLogger(__name__)


class AccountTax(models.Model):
    _inherit = "account.tax"

    def _prepare_tax_totals(
        self,
        base_lines,
        currency,
        is_company_currency_requested=False,
        tax_lines=None,
        igtf_base_amount=False,
    ):
        """
        This function add values and calculated of igtf on invoices
        ---------------
        Returns: (Return inherited)
        We add the following values to the dictionary:
            - igtf :
                - igtf_base_amount: float
                - igtf_amount: float
                - foreign_igtf_amount: float
                - foreign_igtf_base_amount: float
                - formatted_igtf_amount: str
                - formatted_igtf_base_amount: str
                - formatted_foreign_igtf_amount: str
                - formatted_foreign_igtf_base_amount: str
                - apply_igtf: bool
            - amount_total_igtf : float
            - formatted_amount_total_igtf: str
            - foreign_amount_total_igtf: float
            - formatted_foreign_amount_total_igtf: str
        """
        res = super()._prepare_tax_totals(
            base_lines,
            currency,
            tax_lines,
            is_company_currency_requested=is_company_currency_requested,
        )

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

        foreign_currency = self.env.company.currency_foreign_id
        rate = 0

        if type_model == "account.move.line":
            rate = invoice.foreign_inverse_rate
        if type_model == "sale.order.line":
            rate = order.foreign_inverse_rate

        float_igtf_percentage = (
            self.env.company.igtf_percentage if not invoice.is_two_percentage else 2
        )
        igtf_percentage = (float_igtf_percentage or 0) / 100

        if type_model == "account.move.line" and self.env.company.show_igtf_suggested_account_move:
            is_igtf_suggested = True
            base_igtf = res.get("amount_total", 0)
            foreign_base_igtf = res.get("foreign_amount_total", 0)
        if type_model == "sale.order.line" and self.env.company.show_igtf_suggested_sale_order:
            is_igtf_suggested = True
            base_igtf = res.get("amount_total", 0)
            foreign_base_igtf = res.get("foreign_amount_total", 0)

        if invoice.bi_igtf:
            is_igtf_suggested = False
            base_igtf = invoice.bi_igtf
            foreign_base_igtf = invoice.bi_igtf * rate
            if invoice.bi_igtf == res.get("amount_total"):
                foreign_base_igtf = res.get("foreign_amount_total")

        igtf_base_amount = float_round(base_igtf or 0, precision_rounding=currency.rounding)
        igtf_foreign_base_amount = float_round(
            foreign_base_igtf or 0, precision_rounding=foreign_currency.rounding
        )

        if float_is_zero(igtf_base_amount, precision_rounding=currency.rounding) == False:
            apply_igtf = True

        foreign_igtf_base_amount = float_round(
            igtf_foreign_base_amount, precision_rounding=foreign_currency.rounding
        )

        igtf_amount = float_round(
            igtf_base_amount * igtf_percentage, precision_rounding=currency.rounding
        )
        foreign_igtf_amount = float_round(
            foreign_igtf_base_amount * igtf_percentage, precision_rounding=foreign_currency.rounding
        )

        res["igtf"] = {}
        res["igtf"]["apply_igtf"] = apply_igtf
        res["igtf"]["name"] = f"{float_igtf_percentage} %"

        res["igtf"]["igtf_base_amount"] = igtf_base_amount
        res["igtf"]["igtf_amount"] = igtf_amount
        res["igtf"]["foreign_igtf_amount"] = foreign_igtf_amount
        res["igtf"]["foreign_igtf_base_amount"] = foreign_igtf_base_amount

        res["igtf"]["formatted_igtf_amount"] = formatLang(
            self.env, igtf_amount, currency_obj=currency
        )
        res["igtf"]["formatted_igtf_base_amount"] = formatLang(
            self.env, igtf_base_amount, currency_obj=currency
        )
        res["igtf"]["formatted_foreign_igtf_amount"] = formatLang(
            self.env, foreign_igtf_amount, currency_obj=foreign_currency
        )
        res["igtf"]["formatted_foreign_igtf_base_amount"] = formatLang(
            self.env, foreign_igtf_base_amount, currency_obj=foreign_currency
        )

        res["amount_total_igtf"] = float_round(
            res["amount_total"] + igtf_amount, precision_rounding=currency.rounding
        )
        res["formatted_amount_total_igtf"] = formatLang(
            self.env, res["amount_total_igtf"], currency_obj=currency
        )
        res["foreign_amount_total_igtf"] = float_round(
            res["foreign_amount_total"] + foreign_igtf_amount,
            precision_rounding=foreign_currency.rounding,
        )
        res["formatted_foreign_amount_total_igtf"] = formatLang(
            self.env, res["foreign_amount_total_igtf"], currency_obj=foreign_currency
        )
        res["igtf"]["is_igtf_suggested"] = is_igtf_suggested

        return res
