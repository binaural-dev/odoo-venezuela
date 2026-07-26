from odoo.tools.float_utils import float_round, float_compare
from odoo import api, models, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools.misc import formatLang

import logging

_logger = logging.getLogger(__name__)


class AccountTax(models.Model):
    _inherit = "account.tax"

    @api.model
    def _prepare_tax_totals(
        self, base_lines, currency, tax_lines=None, is_company_currency_requested=False
    ):
        foreign_currency = self.env.company.currency_foreign_id or False
        if not foreign_currency:
            raise ValidationError(_("No foreign currency configured in the company"))

        res = super()._prepare_tax_totals(
            base_lines, currency, tax_lines,
            is_company_currency_requested=is_company_currency_requested,
        )

        move = self._get_move_from_base_lines(base_lines)
        if move and move._name == 'account.move' and move.is_invoice(include_receipts=True):
            if move.currency_id and move.company_id.currency_id and move.currency_id != move.company_id.currency_id:
                product_lines = move.line_ids.filtered(
                    lambda l: l.display_type == 'product' and not l.tax_repartition_line_id
                )
                if product_lines:
                    cc = move.company_id.currency_id
                    sign = move.direction_sign
                    correct_base = cc.round(sum(product_lines.mapped('balance')) * sign)
                    current_base = res.get('base_amount', 0.0)
                    diff = cc.round(correct_base - current_base)
                    if not cc.is_zero(diff):
                        res['base_amount'] = correct_base
                        res['total_amount'] = cc.round(res.get('total_amount', 0.0) + diff)
                        subtotals = res.get('subtotals', [])
                        if subtotals:
                            total_sub_base = sum(s.get('base_amount', 0.0) for s in subtotals)
                            if not cc.is_zero(total_sub_base):
                                remaining_diff = diff
                                n_sub = len(subtotals)
                                for i, subtotal in enumerate(subtotals):
                                    if i < n_sub - 1:
                                        ratio = subtotal.get('base_amount', 0.0) / total_sub_base
                                        share = cc.round(ratio * diff)
                                        subtotal['base_amount'] = subtotal.get('base_amount', 0.0) + share
                                        subtotal['total_amount'] = subtotal.get('total_amount', 0.0) + share
                                        remaining_diff -= share
                                    else:
                                        subtotal['base_amount'] = subtotal.get('base_amount', 0.0) + remaining_diff
                                        subtotal['total_amount'] = subtotal.get('total_amount', 0.0) + remaining_diff
                                    tax_groups = subtotal.get('tax_groups', [])
                                    if tax_groups:
                                        tg_total = sum(tg.get('base_amount', 0.0) for tg in tax_groups)
                                        if not cc.is_zero(tg_total):
                                            n_tg = len(tax_groups)
                                            for j, tg in enumerate(tax_groups):
                                                if j < n_tg - 1:
                                                    tg_ratio = tg.get('base_amount', 0.0) / tg_total
                                                    tg_share = cc.round(tg_ratio * subtotal['base_amount'])
                                                    tg['base_amount'] = tg_share
                                                    tg['display_base_amount'] = tg_share
                                                    tg['total_amount'] = cc.round(tg.get('tax_amount', 0.0) + tg_share)
                                                else:
                                                    tg['base_amount'] = subtotal['base_amount'] - sum(
                                                        tax_groups[k]['base_amount'] for k in range(j)
                                                    )
                                                    tg['display_base_amount'] = tg['base_amount']
                                                    tg['total_amount'] = cc.round(tg.get('tax_amount', 0.0) + tg['base_amount'])

        res_without_discount = res.copy()
        has_discount = not currency.is_zero(sum([line["discount"] for line in base_lines]))

        if has_discount:
            base_without_discount = [line.copy() for line in base_lines if line]
            for base_line in base_without_discount:
                base_line["discount"] = 0
            res_without_discount = super()._prepare_tax_totals(
                base_without_discount, currency, tax_lines,
                is_company_currency_requested=is_company_currency_requested,
            )

        foreign_base_lines, foreign_tax_lines = self._get_foreign_base_tax_lines(
            base_lines, tax_lines, foreign_currency
        )

        foreign_taxes = super()._prepare_tax_totals(
            foreign_base_lines, foreign_currency, None,
            is_company_currency_requested=is_company_currency_requested,
        )

        fc = move.company_id.currency_foreign_id if move else self.env.company.currency_foreign_id
        if move and move.is_invoice(include_receipts=True):
            expected_total = fc.round(abs(move.amount_total) * move.foreign_inverse_rate)
            current_total = foreign_taxes.get("amount_total", 0.0)
            diff = fc.round(expected_total - current_total)
            if not fc.is_zero(diff):
                foreign_taxes["amount_total"] = expected_total
                foreign_taxes["amount_untaxed"] = fc.round(foreign_taxes["amount_untaxed"] + diff)
                subtotals = foreign_taxes.get("subtotals", [])
                if subtotals:
                    total_sub = sum(s.get("amount", 0.0) for s in subtotals)
                    if not fc.is_zero(total_sub):
                        remaining = diff
                        n = len(subtotals)
                        for i, sub in enumerate(subtotals):
                            if i < n - 1:
                                ratio = sub.get("amount", 0.0) / total_sub
                                share = fc.round(ratio * diff)
                                sub["amount"] = fc.round(sub["amount"] + share)
                                remaining -= share
                            else:
                                sub["amount"] = fc.round(sub["amount"] + remaining)
                            sub["formatted_amount"] = formatLang(self.env, sub["amount"], currency_obj=foreign_currency)
                foreign_taxes["formatted_amount_total"] = formatLang(
                    self.env, expected_total, currency_obj=foreign_currency,
                )
                foreign_taxes["formatted_amount_untaxed"] = formatLang(
                    self.env, foreign_taxes["amount_untaxed"], currency_obj=foreign_currency,
                )

        foreign_taxes_without_discount = foreign_taxes.copy()
        if has_discount:
            foreign_without_discount = [line.copy() for line in foreign_base_lines if line]
            for foreign_base_line in foreign_without_discount:
                foreign_base_line["discount"] = 0
            foreign_taxes_without_discount = super()._prepare_tax_totals(
                foreign_without_discount, foreign_currency, None,
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

        foreign_amount_total = res.get("foreign_amount_total", 0.0)
        foreign_amount_residual = foreign_amount_total
        if move and move.payment_state in ('partial', 'paid', 'in_payment'):
            foreign_amount_residual = move.foreign_amount_residual or foreign_amount_total
        res["foreign_total_amount_paid"] = foreign_amount_total - foreign_amount_residual
        res["foreign_total_residual"] = foreign_amount_residual
        res["foreign_formatted_total_residual"] = formatLang(
            self.env, foreign_amount_residual, currency_obj=foreign_currency
        )

        return res

    def _get_move_from_base_lines(self, base_lines):
        for l in (base_lines or []):
            r = l.get("record")
            if not r:
                continue
            if getattr(r, "_name", None) == "account.move":
                return r
            if "move_id" in getattr(r, "_fields", {}):
                if r.move_id:
                    return r.move_id
        return None

    def _get_foreign_base_tax_lines(self, base_lines, tax_lines, currency):
        foreign_base_lines = [line.copy() for line in base_lines if line]
        foreign_tax_lines = None
        if tax_lines:
            foreign_tax_lines = [line.copy() for line in tax_lines if line]
            for tax_line in foreign_tax_lines:
                tax_line["currency"] = currency

        for base_line in foreign_base_lines:
            record = base_line.get("record")
            if record and hasattr(record, "foreign_price"):
                base_line["price_unit"] = record.foreign_price
                base_line["price_subtotal"] = record.foreign_subtotal
                base_line["currency"] = currency

        return foreign_base_lines, foreign_tax_lines