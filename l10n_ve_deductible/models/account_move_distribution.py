import math

from odoo import models

EPS = 1e-9


class AccountMove(models.Model):
    """How the deductible is spread over the product lines of a document."""

    _inherit = "account.move"

    def _get_deductible_product_lines(self):
        self.ensure_one()
        return self.invoice_line_ids.filtered(lambda line: line.display_type == "product")

    def _get_deductible_gross_total(self):
        """Sum of price_unit * quantity of the product lines (no discount)."""
        return sum(line.price_unit * line.quantity for line in self._get_deductible_product_lines())

    def _get_deductible_line_amounts(self):
        """{line: amount taken off} in the document currency (fixed mode).
        The lines whose amount was typed by the user (`global_deductible_manual`)
        keep it; what is left of the amount of the document is spread over the
        others proportionally to their gross, in cents, with the lost cents
        given back by largest remainder and no line reaching its own subtotal,
        so the amounts add up exactly to the amount entered."""
        self.ensure_one()
        gross = {line: line.price_unit * line.quantity for line in self._get_deductible_product_lines()}
        gross = {line: value for line, value in gross.items() if value > 0}
        total, amount = sum(gross.values()), self.global_deductible_amount
        if (
            not self.is_deductible
            or self.global_deductible_type != "amount"
            or not self.currency_id
            or not 0.0 < amount < total
        ):
            return {}
        fixed = {line: line.global_deductible_line_amount for line in gross if line.global_deductible_manual}
        free = {line: value for line, value in gross.items() if line not in fixed}
        amounts = dict(fixed)
        amounts.update(dict.fromkeys(free, 0.0))
        left = amount - sum(fixed.values())
        if free and left > 0:
            amounts.update(self._spread_deductible_amount(left, free))
        return amounts

    def _spread_deductible_amount(self, amount, gross):
        """{line: share} of `amount` over the lines in `gross` ({line: gross})."""
        total = sum(gross.values())
        rounding = self.currency_id.rounding
        ideal = {line: amount * value / total / rounding for line, value in gross.items()}
        cap = {line: max(math.ceil(value / rounding - EPS) - 1, 0) for line, value in gross.items()}
        units = {line: min(math.floor(ideal[line] + EPS), cap[line]) for line in gross}
        leftover = round(amount / rounding) - sum(units.values())
        by_remainder = sorted(gross, key=lambda line: units[line] - ideal[line])
        while leftover > 0:
            room = [line for line in by_remainder if units[line] < cap[line]][:leftover]
            if not room:
                break
            for line in room:
                units[line] += 1
            leftover -= len(room)
        return {line: self.currency_id.round(count * rounding) for line, count in units.items()}

    def _get_deductible_line_percents(self):
        """{line: exact discount %}: the document's % on every line, or in
        fixed mode `amount / gross * 100` (the formula of `discount_fixed`)
        with the amount each line holds (`global_deductible_line_amount`: the
        automatic share, or what the user typed in the line)."""
        self.ensure_one()
        if not self.is_deductible:
            return {}
        if self.global_deductible_type == "percent":
            percent = self.global_deductible_percent
            valid = percent if 0.0 < percent < 100.0 else 0.0
            return dict.fromkeys(self._get_deductible_product_lines(), valid)
        percents = {}
        for line in self._get_deductible_product_lines():
            gross = line.price_unit * line.quantity
            if gross > 0 and line.global_deductible_line_amount:
                percents[line] = (line.global_deductible_line_amount / gross) * 100.0
        return percents
