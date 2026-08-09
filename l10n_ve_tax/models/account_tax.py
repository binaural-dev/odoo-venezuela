import math

from odoo.tools.float_utils import float_round, float_compare
from odoo import api, fields, models, _
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
        if move and move._name == 'account.move' and move.is_invoice(include_receipts=True) and move.line_ids:
            self._sync_foreign_taxes_with_entry(move, foreign_taxes, fc, foreign_currency)
        elif move and move._name in ('sale.order', 'purchase.order') and move.order_line:
            self._anchor_foreign_taxes_for_order(move, foreign_taxes, fc, foreign_currency)

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
        if move and move._name == 'account.move' and move.payment_state in ('partial', 'paid', 'in_payment'):
            foreign_amount_residual = move.foreign_amount_residual or foreign_amount_total
        res["foreign_total_amount_paid"] = foreign_amount_total - foreign_amount_residual
        res["foreign_total_residual"] = foreign_amount_residual
        res["foreign_formatted_total_residual"] = formatLang(
            self.env, foreign_amount_residual, currency_obj=foreign_currency
        )

        return res

    def _apportion_largest_remainder(self, groups, key, target_total, decimal_places):
        """Round each groups[i][key] so they sum exactly to target_total,
        handing out the leftover cents to the entries with the largest
        fractional remainder (deterministic, no arbitrary single-line
        patch). Mirrors account.move's helper of the same name/purpose.

        The bulk of the gap between the sum of floors and the target is
        distributed in one `divmod` pass (O(n)), and only the last few
        units are handed out one by one to the largest remainders --
        never a naive one-cent-at-a-time loop over the whole gap, which
        would be O(remaining) and can hang for minutes when the ideal
        values are wildly off-scale from the target (e.g. a bug upstream).
        """
        n = len(groups)
        if n == 0:
            return
        scale = 10 ** decimal_places
        values = [groups[i].get(key, 0.0) for i in range(n)]
        target_scaled = round(target_total * scale)
        signs = [1 if v >= 0 else -1 for v in values]
        scaled = [abs(v) * scale for v in values]
        floors = [math.floor(v) for v in scaled]
        remainders = [s - f for s, f in zip(scaled, floors)]
        result = floors[:]
        remaining = target_scaled - sum(s * f for s, f in zip(signs, floors))
        order = sorted(range(n), key=lambda i: -remainders[i])
        if remaining != 0:
            base, extra = divmod(abs(remaining), n)
            step = 1 if remaining > 0 else -1
            for i in range(n):
                result[i] += step * base
            for i in range(extra):
                result[order[i]] += step
        idx = 0
        order_rev = list(reversed(order))
        while any(v < 0 for v in result):
            neg_idx = next(i for i, v in enumerate(result) if v < 0)
            donor = order_rev[idx % n]
            if result[donor] > 0:
                result[donor] -= 1
                result[neg_idx] += 1
            idx += 1
            if idx > n * 4:
                break
        for i in range(n):
            groups[i][key] = signs[i] * (result[i] / scale)

    def _sync_foreign_taxes_with_entry(self, move, foreign_taxes, fc, foreign_currency):
        """Make the widget's foreign breakdown (`groups_by_subtotal`,
        `subtotals`, `amount_untaxed`/`amount_total`) match what's actually
        posted on the journal entry, instead of an independent re-tax of
        each product's `foreign_price` (which used to only get reconciled
        with the entry at the grand-total level, leaving the per-tax-group
        breakdown -- e.g. the 8%/16%/31% split -- a few cents off from what
        was really posted).

        `foreign_subtotal` already carries the natural sign of the price
        (negative for a discount/credit line) regardless of move type, so
        it is summed as-is. `foreign_debit - foreign_credit` instead follows
        the ledger's debit/credit convention, which flips between inbound
        (out_invoice) and outbound (in_invoice) documents -- `direction_sign`
        normalizes that back to the same "positive means charge" convention
        as the base, so mixed-sign lines (e.g. a negative discount line next
        to a normal one) cancel out correctly instead of every line's
        magnitude being added regardless of sign (the bug from #14341 this
        used to reintroduce via `abs()`).

        `product_foreign`/`tax_foreign` (the real entry totals every group
        must reconcile to) are signed for the same reason; the final total
        is wrapped in `abs()` in `_finalize_foreign_taxes` since the
        document-level amount is conventionally shown as a magnitude.
        """
        sign = move.direction_sign
        base_by_group = {}
        tax_by_group = {}
        for line in move.line_ids:
            if line.display_type == 'product':
                for tax in line.tax_ids:
                    grp_id = tax.tax_group_id.id
                    base_by_group[grp_id] = base_by_group.get(grp_id, 0.0) + line.foreign_subtotal
            elif line.display_type == 'tax' and line.tax_repartition_line_id:
                grp_id = line.tax_repartition_line_id.tax_id.tax_group_id.id
                tax_by_group[grp_id] = tax_by_group.get(grp_id, 0.0) + sign * (line.foreign_debit - line.foreign_credit)

        all_groups = [
            g
            for groups in (foreign_taxes.get("groups_by_subtotal") or {}).values()
            for g in groups
        ]
        for g in all_groups:
            grp_id = g.get("tax_group_id")
            g["tax_group_base_amount"] = base_by_group.get(grp_id, g.get("tax_group_base_amount", 0.0))
            g["tax_group_amount"] = tax_by_group.get(grp_id, g.get("tax_group_amount", 0.0))

        product_foreign = sum(
            line.foreign_subtotal for line in move.line_ids if line.display_type == 'product')
        tax_foreign = sign * sum(
            (line.foreign_debit - line.foreign_credit)
            for line in move.line_ids if line.display_type == 'tax')

        self._finalize_foreign_taxes(
            foreign_taxes, all_groups, product_foreign, tax_foreign, fc, foreign_currency)

    def _anchor_foreign_taxes_for_order(self, order, foreign_taxes, fc, foreign_currency):
        """Anchor a sale.order's or purchase.order's (quotation/RFQ's) alterno
        tax_totals to `amount_total x rate`, the same invariant
        `_sync_foreign_taxes_with_entry` enforces for a posted account.move --
        so a quotation/RFQ shows the same alterno total the resulting
        invoice/bill will show once posted, instead of an independent
        per-line re-tax (each line's `foreign_price` rounded on its own) that
        can drift a few units of the alterno currency away from the direct
        conversion.

        Neither model has posted journal lines to read the real tax amount
        from (unlike an invoice), so the widget's own per-group tax amounts
        (already computed by the base `_prepare_tax_totals` from each line's
        `foreign_price`) are used as the *ideal* starting point, and only the
        gap between their sum and the true anchor is apportioned across them.
        """
        rate = order.foreign_inverse_rate or 0.0
        if not rate:
            return
        rate_date = order.date_order.date() if order.date_order else fields.Date.context_today(order)
        if order.currency_id == fc:
            target_total = fc.round(abs(order.amount_total))
        else:
            target_total = fc.round(order.currency_id._convert(
                abs(order.amount_total), fc, order.company_id, rate_date,
                custom_rate=rate,
            ))

        product_lines = order.order_line.filtered(lambda l: not l.display_type)
        if not product_lines:
            return
        product_foreign = sum(product_lines.mapped('foreign_subtotal'))

        all_groups = [
            g
            for groups in (foreign_taxes.get("groups_by_subtotal") or {}).values()
            for g in groups
        ]
        if not all_groups:
            return

        tax_foreign = target_total - product_foreign
        self._finalize_foreign_taxes(
            foreign_taxes, all_groups, product_foreign, tax_foreign, fc, foreign_currency)

    def _finalize_foreign_taxes(self, foreign_taxes, all_groups, product_foreign, tax_foreign, fc, foreign_currency):
        """Shared tail of `_sync_foreign_taxes_with_entry` and
        `_anchor_foreign_taxes_for_order`: apportion `all_groups`' base/tax
        amounts to sum exactly to `product_foreign`/`tax_foreign`, then
        refresh every derived formatted/subtotal/total field from them.
        """
        if all_groups:
            self._apportion_largest_remainder(
                all_groups, "tax_group_base_amount", product_foreign, fc.decimal_places)
            self._apportion_largest_remainder(
                all_groups, "tax_group_amount", tax_foreign, fc.decimal_places)

        for g in all_groups:
            g["formatted_tax_group_base_amount"] = formatLang(
                self.env, g["tax_group_base_amount"], currency_obj=foreign_currency)
            g["formatted_tax_group_amount"] = formatLang(
                self.env, g["tax_group_amount"], currency_obj=foreign_currency)

        for subtotal_name, groups in (foreign_taxes.get("groups_by_subtotal") or {}).items():
            subtotal_untaxed = fc.round(sum(g["tax_group_base_amount"] for g in groups))
            for sub in foreign_taxes.get("subtotals", []):
                if sub.get("name") == subtotal_name:
                    sub["amount"] = subtotal_untaxed
                    sub["formatted_amount"] = formatLang(
                        self.env, subtotal_untaxed, currency_obj=foreign_currency)

        foreign_taxes["amount_untaxed"] = fc.round(product_foreign)
        foreign_taxes["amount_total"] = fc.round(abs(product_foreign + tax_foreign))
        foreign_taxes["formatted_amount_untaxed"] = formatLang(
            self.env, foreign_taxes["amount_untaxed"], currency_obj=foreign_currency)
        foreign_taxes["formatted_amount_total"] = formatLang(
            self.env, foreign_taxes["amount_total"], currency_obj=foreign_currency)

    def _get_move_from_base_lines(self, base_lines):
        for l in (base_lines or []):
            r = l.get("record")
            if not r:
                continue
            if getattr(r, "_name", None) in ("account.move", "sale.order"):
                return r
            if "move_id" in getattr(r, "_fields", {}):
                if r.move_id:
                    return r.move_id
            if "order_id" in getattr(r, "_fields", {}):
                if r.order_id:
                    return r.order_id
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