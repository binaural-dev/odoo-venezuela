from collections import defaultdict
from odoo import api, models, _


class AccountTax(models.Model):
    _inherit = "account.tax"

    @api.model
    def _prepare_tax_totals(self, base_lines, currency, tax_lines=None):
        """
        This function adds the alternate currency tax amounts to tax_totals.
        In it, the parent function is executed 2 times, once for the original
        currency and once for the alternate currency.

        The data that is brought is not recalculated, that is, it comes from the lines of the entry
        ------
        Parameters: (Parameters inherited)
            base_lines: list of dict
            currency: res.currency
        ------
        Returns: (Return inherited)
            dict: Now returns additionally:
            "groups_by_foreign_subtotal": dict
            "foreign_subtotals": list of dict
            "foreign_amount_untaxed": float
            "foreign_amount_total": float
            "foreign_formatted_amount_untaxed": str
            "foreign_formatted_amount_total": str
        """
        foreign_currency = self.env["res.currency"]
        for base_line in base_lines:
            if base_line["record"].move_id.foreign_currency_id:
                foreign_currency = base_line["record"].move_id.foreign_currency_id
                break
        res = super()._prepare_tax_totals(base_lines, currency, tax_lines)

        if not foreign_currency:
            foreign_currency = self.env.company.currency_foreign_id or False

        taxes = []

        for base_line in base_lines:
            base_line["price_unit"] = base_line["record"].foreign_price
            base_line["price_subtotal"] = base_line["record"].foreign_subtotal
            base_line["currency"] = foreign_currency

            if base_line["taxes"]:
                taxes.append({"tax": base_line["taxes"][0], "base": base_line["price_subtotal"]})

        if tax_lines:
            for tax_line in tax_lines:
                tax_line["currency"] = foreign_currency
                tax_line["tax_amount"] = 0.0
                for tax in taxes:
                    if tax_line["tax_repartition_line"].invoice_tax_id.id == tax["tax"].id:
                        tax_line["tax_amount"] += tax["base"] * (
                            tax_line["tax_repartition_line"].invoice_tax_id.amount / 100
                        )

        foreign_taxes = super()._prepare_tax_totals(base_lines, foreign_currency, tax_lines)

        res["groups_by_foreign_subtotal"] = foreign_taxes["groups_by_subtotal"]
        res["foreign_subtotals"] = foreign_taxes["subtotals"]
        res["foreign_amount_untaxed"] = foreign_taxes["amount_untaxed"]
        res["foreign_amount_total"] = foreign_taxes["amount_total"]
        res["foreign_formatted_amount_untaxed"] = foreign_taxes["formatted_amount_untaxed"]
        res["foreign_formatted_amount_total"] = foreign_taxes["formatted_amount_total"]
        return res
