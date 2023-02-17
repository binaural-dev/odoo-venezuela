from odoo import api, models, _


class AccountTax(models.Model):
    _inherit = "account.tax"

    @api.model
    def _prepare_tax_totals(self, base_lines, currency, tax_lines=None):
        """
        This function calculates the total taxes in the alternate currency,
        calling itself 2 times, once in its original currency and once with
        the amounts multiplied by the rate of the alternate currency.
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
            return res

        for base_line in base_lines:
            rate = base_line["record"].move_id.foreign_inverse_rate

            base_line["price_unit"] = base_line["price_unit"] * rate
            base_line["price_subtotal"] = base_line["price_subtotal"] * rate
            base_line["currency"] = foreign_currency

        if tax_lines:
            for tax_line in tax_lines:
                rate = tax_line["record"].move_id.foreign_inverse_rate
                tax_line["currency"] = foreign_currency
                tax_line["tax_amount"] = tax_line["tax_amount"] * rate

        foreign_taxes = super()._prepare_tax_totals(base_lines, foreign_currency, tax_lines)

        res["groups_by_foreign_subtotal"] = foreign_taxes["groups_by_subtotal"]
        res["foreign_subtotals"] = foreign_taxes["subtotals"]
        res["foreign_amount_untaxed"] = foreign_taxes["amount_untaxed"]
        res["foreign_amount_total"] = foreign_taxes["amount_total"]
        res["foreign_formatted_amount_untaxed"] = foreign_taxes["formatted_amount_untaxed"]
        res["foreign_formatted_amount_total"] = foreign_taxes["formatted_amount_total"]
        return res
