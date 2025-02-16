from odoo.tools.float_utils import float_round
from odoo import api, models, _
from odoo.exceptions import ValidationError
from odoo.tools.misc import formatLang

import logging

_logger = logging.getLogger(__name__)


class AccountTax(models.Model):
    _inherit = "account.tax"

    @api.model
    def _prepare_tax_totals(
        self, base_lines, currency, tax_lines=None, is_company_currency_requested=False
    ):
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
            "subtotal": float
            "formatted_subtotal": str
            "discount_amount": float
            "foreign_subtotal": float
            "foreign_formatted_subtotal": str
            "formatted_discount_amount": str
            "groups_by_foreign_subtotal": dict
            "foreign_discount_amount": float
            "foreign_formatted_discount_amount": str
            "foreign_subtotals": list of dict
            "foreign_amount_untaxed": float
            "foreign_amount_total": float
            "foreign_formatted_amount_untaxed": str
            "foreign_formatted_amount_total": str
        """
        foreign_currency = self.env.company.currency_foreign_id or False
        if not foreign_currency:
            raise ValidationError(_("No foreign currency configured in the company"))

        # Base Currency
        res = super()._prepare_tax_totals(
            base_lines,
            currency,
            tax_lines,
            is_company_currency_requested=is_company_currency_requested,
        )
        res_without_discount = res.copy()
        has_discount = not currency.is_zero(sum([line["discount"] for line in base_lines]))

        if has_discount:
            base_without_discount = [line.copy() for line in base_lines if line]
            for base_line in base_without_discount:
                base_line["discount"] = 0

            res_without_discount = super()._prepare_tax_totals(
                base_without_discount,
                currency,
                tax_lines,
                is_company_currency_requested=is_company_currency_requested,
            )

        foreign_base_lines, foreign_tax_lines = self.get_foreign_base_tax_lines(
            base_lines, tax_lines, foreign_currency
        )

        # Foreign Currency
        foreign_taxes = super()._prepare_tax_totals(
            foreign_base_lines,
            foreign_currency,
            foreign_tax_lines,
            is_company_currency_requested=is_company_currency_requested,
        )

        foreign_taxes_without_discount = foreign_taxes.copy()
        if has_discount:
            foreign_without_discount = [line.copy() for line in foreign_base_lines if line]
            for foreign_base_line in foreign_without_discount:
                foreign_base_line["discount"] = 0

            foreign_taxes_without_discount = super()._prepare_tax_totals(
                foreign_without_discount,
                foreign_currency,
                foreign_tax_lines,
                is_company_currency_requested=is_company_currency_requested,
            )

        res["groups_by_foreign_subtotal"] = foreign_taxes["groups_by_subtotal"]
        res["foreign_subtotals"] = foreign_taxes["subtotals"]
        res["foreign_amount_untaxed"] = foreign_taxes["amount_untaxed"]
        res["foreign_amount_total"] = foreign_taxes["amount_total"]
        res["foreign_formatted_amount_untaxed"] = foreign_taxes["formatted_amount_untaxed"]
        res["foreign_formatted_amount_total"] = foreign_taxes["formatted_amount_total"]

        res["show_discount"] = self.env.company.show_discount_on_moves

        res["subtotal"] = res_without_discount["amount_untaxed"]
        res["formatted_subtotal"] = formatLang(self.env, res["subtotal"], currency_obj=currency)

        res["foreign_subtotal"] = foreign_taxes_without_discount["amount_untaxed"]
        res["foreign_formatted_subtotal"] = formatLang(
            self.env, res["foreign_subtotal"], currency_obj=foreign_currency
        )

        res["discount_amount"] = res["amount_untaxed"] - res_without_discount["amount_untaxed"]
        res["formatted_discount_amount"] = formatLang(
            self.env, res["discount_amount"], currency_obj=currency
        )
        res["foreign_discount_amount"] = (
            foreign_taxes["amount_untaxed"] - foreign_taxes_without_discount["amount_untaxed"]
        )
        res["foreign_formatted_discount_amount"] = formatLang(
            self.env, res["foreign_discount_amount"], currency_obj=foreign_currency
        )
        return res

    def get_foreign_base_tax_lines(self, base_lines, tax_lines, currency):
        foreign_base_lines = [line.copy() for line in base_lines if line]
        foreign_tax_lines = None
        if tax_lines:
            foreign_tax_lines = [line.copy() for line in tax_lines if line]
        taxes = []
        for base_line in foreign_base_lines:
            is_exists_foreign_price = "foreign_price" in base_line["record"]

            if is_exists_foreign_price:
                base_line["price_unit"] = base_line["record"].foreign_price
                base_line["price_subtotal"] = base_line["record"].foreign_subtotal
                base_line["currency"] = currency
            else:
                base_line["price_unit"] = base_line["record"].price_unit
                base_line["price_subtotal"] = base_line["record"].price_subtotal
                base_line["currency"] = base_line["record"].currency_id

            if base_line["taxes"]:
                taxes.append(
                    {
                        "tax": base_line["taxes"][0],
                        "price": base_line["price_unit"],
                        "base": base_line["price_subtotal"],
                    }
                )

        tax_values_list = []
        for base_line in foreign_base_lines:
            tax_values_list += self._compute_taxes_for_single_line(base_line)[1]

        round_globally = self.env.company.tax_calculation_rounding_method == "round_globally"

        if foreign_tax_lines:
            for tax_line in foreign_tax_lines:
                tax_line["currency"] = currency
                tax_line["tax_amount"] = 0.0
                amount = 0.0
                for tax in tax_values_list:
                    if tax["tax_repartition_line"].id == tax_line["tax_repartition_line"].id:
                        if not round_globally:
                            amount += float_round(
                                tax["amount"], precision_digits=currency.decimal_places
                            )
                        else:
                            amount += tax["amount"]

                tax_line["tax_amount"] = float_round(
                    amount, precision_digits=currency.decimal_places
                )

        return foreign_base_lines, foreign_tax_lines
