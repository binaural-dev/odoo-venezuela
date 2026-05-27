from odoo import models, _
from odoo.tools.misc import formatLang

import logging

_logger = logging.getLogger(__name__)


class AccountTax(models.Model):
    _inherit = "account.tax"

    def _prepare_tax_totals(
        self, base_lines, currency, tax_lines=None, igtf_base_amount=False, is_company_currency_requested=False
    ):
        res = super()._prepare_tax_totals(
            base_lines, currency, tax_lines, is_company_currency_requested=is_company_currency_requested
        )

        invoice = False
        order = False
        type_model = ""
        is_igtf_suggested = False

        for base_line in base_lines:
            type_model = base_line["record"]._name
            if type_model == "account.move.line":
                invoice = base_line["record"].move_id
            if type_model == "sale.order.line":
                order = base_line["record"].order_id

        float_igtf_percentage = self.env.company.igtf_percentage or 0.0
        igtf_percentage = float_igtf_percentage / 100.0

        base_igtf_bs = 0.0
        foreign_base_igtf = 0.0

        if type_model == "account.move.line" and invoice:
            if self.env.company.show_igtf_suggested_account_move and invoice.payment_state == "not_paid":
                is_igtf_suggested = True
                base_igtf_bs = res.get("amount_total", 0.0)
                foreign_base_igtf = res.get("foreign_amount_total", 0.0)
            
            elif hasattr(invoice, 'bi_igtf') and invoice.bi_igtf:
                base_igtf_bs = invoice.bi_igtf
                amount_total_bs = res.get("amount_total", 0.0)
                if amount_total_bs > 0.0:
                    porcion_base_igtf = base_igtf_bs / amount_total_bs
                    foreign_base_igtf = res.get("foreign_amount_total", 0.0) * porcion_base_igtf
                else:
                    foreign_base_igtf = getattr(invoice, 'foreign_bi_igtf', 0.0) or base_igtf_bs

        elif type_model == "sale.order.line" and order:
            if self.env.company.show_igtf_suggested_sale_order:
                is_igtf_suggested = True
                base_igtf_bs = res.get("amount_total", 0.0)
                foreign_base_igtf = res.get("foreign_amount_total", 0.0)
            elif hasattr(order, 'bi_igtf') and order.bi_igtf:
                base_igtf_bs = order.bi_igtf
                amount_total_bs = res.get("amount_total", 0.0)
                if amount_total_bs > 0.0:
                    porcion_base_igtf = base_igtf_bs / amount_total_bs
                    foreign_base_igtf = res.get("foreign_amount_total", 0.0) * porcion_base_igtf
                else:
                    foreign_base_igtf = base_igtf_bs

        apply_igtf = not currency.is_zero(base_igtf_bs)

        igtf_amount_bs = base_igtf_bs * igtf_percentage
        foreign_igtf_amount = foreign_base_igtf * igtf_percentage
        foreign_currency_id = self.env.company.currency_foreign_id
        res["igtf"] = {
            "apply_igtf": apply_igtf,
            "name": f"{float_igtf_percentage} %",
            "is_igtf_suggested": is_igtf_suggested,
            
            "igtf_base_amount": base_igtf_bs,
            "formatted_igtf_base_amount": formatLang(self.env, base_igtf_bs, currency_obj=currency),
            "foreign_igtf_base_amount": foreign_base_igtf,
            "formatted_foreign_igtf_base_amount": formatLang(self.env, foreign_base_igtf, currency_obj=foreign_currency_id),
            
            "igtf_amount": igtf_amount_bs,
            "formatted_igtf_amount": formatLang(self.env, igtf_amount_bs, currency_obj=currency),
            "foreign_igtf_amount": foreign_igtf_amount,
            "formatted_foreign_igtf_amount": formatLang(self.env, foreign_igtf_amount, currency_obj=foreign_currency_id),
        }

        res["amount_total_igtf"] = res.get("amount_total", 0.0) + igtf_amount_bs
        res["formatted_amount_total_igtf"] = formatLang(
            self.env, res["amount_total_igtf"], currency_obj=currency
        )

        res["foreign_amount_total_igtf"] = res.get("foreign_amount_total", 0.0) + foreign_igtf_amount
        res["formatted_foreign_amount_total_igtf"] = formatLang(
            self.env, res["foreign_amount_total_igtf"], currency_obj=foreign_currency_id
        )

        return res