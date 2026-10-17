import math

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import formatLang
from odoo.tools.float_utils import float_compare, float_is_zero, float_round


class AccountMove(models.Model):
    """Global deductible (percentage or fixed amount) for vendor bills.

    The deductible fields are `copy=False`: duplicating a bill does not carry
    the deductible. Credit notes, debit notes and replacements ask for it.
    """

    _inherit = "account.move"

    DEDUCTIBLE_FIELDS = (
        "is_deductible",
        "global_deductible_type",
        "global_deductible_percent",
        "global_deductible_amount",
    )

    use_deductible = fields.Boolean(related="company_id.use_deductible")
    is_deductible = fields.Boolean(
        string="Deductible",
        copy=False,
        tracking=True,
        help="Applies a global deductible (percentage or fixed amount) "
        "spread over every line of the bill.",
    )
    global_deductible_type = fields.Selection(
        [("percent", "Percentage"), ("amount", "Fixed Amount")],
        string="Deductible Type",
        default="percent",
        copy=False,
        tracking=True,
    )
    global_deductible_percent = fields.Float(
        string="Deductible (%)", digits="Discount", copy=False, tracking=True
    )
    global_deductible_amount = fields.Monetary(
        string="Deductible Amount",
        currency_field="currency_id",
        copy=False,
        tracking=True,
    )
    global_deductible_reference_amount = fields.Monetary(
        string="Deducted Amount",
        currency_field="currency_id",
        compute="_compute_deductible_reference_amount",
        help="Reference: total amount removed from the bill by the deductible.",
    )

    @api.model
    def _get_base_line_sync_extra_fields(self):
        return super()._get_base_line_sync_extra_fields() + [
            "global_deductible_discount_percent"
        ]

    def write(self, vals):
        """Block deductible changes on non-draft bills; turning it off resets
        the percentage and the amount."""
        if any(f in vals for f in self.DEDUCTIBLE_FIELDS):
            posted = self.filtered(lambda m: m.state != "draft")
            if posted:
                raise UserError(
                    _(
                        "The deductible can only be changed on draft bills. "
                        "Reset %s to draft first.",
                        ", ".join(posted.mapped("display_name")),
                    )
                )
        if "is_deductible" in vals and not vals["is_deductible"]:
            vals = dict(vals, global_deductible_percent=0.0, global_deductible_amount=0.0)
        return super().write(vals)

    def _get_deductible_copy_values(self):
        """Values that make a document created from this bill (credit note,
        debit note with copied lines, replacement of a reversed bill) keep the
        same deductible. The fields are `copy=False`, so a plain duplicate does
        not carry the deductible; the notes ask for it explicitly."""
        self.ensure_one()
        if not self.is_deductible or self.move_type != "in_invoice":
            return {}
        return {
            "is_deductible": True,
            "global_deductible_type": self.global_deductible_type,
            "global_deductible_percent": self.global_deductible_percent,
            "global_deductible_amount": self.global_deductible_amount,
        }

    def _reverse_moves(self, default_values_list=None, cancel=False):
        """A credit note of a deductible bill keeps the same deductible, so it
        credits exactly what the bill amounted to (the fields are
        `copy=False`, so they must be passed explicitly)."""
        if not default_values_list:
            default_values_list = [{} for _move in self]
        for move, default_values in zip(self, default_values_list):
            default_values.update(move._get_deductible_copy_values())
        return super()._reverse_moves(
            default_values_list=default_values_list, cancel=cancel
        )

    def _get_deductible_product_lines(self):
        self.ensure_one()
        return self.invoice_line_ids.filtered(lambda l: l.display_type == "product")

    def _get_deductible_gross_total(self):
        """Sum of price_unit * quantity of the product lines (no discount)."""
        self.ensure_one()
        return sum(
            line.price_unit * line.quantity
            for line in self._get_deductible_product_lines()
        )

    def _get_deductible_line_amounts(self):
        """{line: amount taken off} in the document currency (fixed mode):
        proportional to each line's gross, in cents, with the lost cents given
        back by largest remainder and no line reaching its own subtotal, so
        the amounts add up exactly to the amount entered."""
        self.ensure_one()
        lines = self._get_deductible_product_lines()
        amounts = dict.fromkeys(lines, 0.0)
        currency = self.currency_id
        gross_by_line = {l: l.price_unit * l.quantity for l in lines}
        gross = sum(gross_by_line.values())
        deducted = self.global_deductible_amount
        if not lines or not currency or not 0.0 < deducted < gross:
            return amounts
        rounding = currency.rounding
        total_units = round(deducted / rounding)
        eps = 1e-9
        eligible = [l for l in lines if gross_by_line[l] > 0]
        ideal = {l: deducted * gross_by_line[l] / gross / rounding for l in eligible}
        cap = {l: max(math.ceil(gross_by_line[l] / rounding - eps) - 1, 0) for l in eligible}
        units = {l: min(math.floor(ideal[l] + eps), cap[l]) for l in eligible}
        remaining = total_units - sum(units.values())
        order = sorted(eligible, key=lambda l: ideal[l] - units[l], reverse=True)
        while remaining > 0:
            progressed = False
            for line in order:
                if remaining and units[line] < cap[line]:
                    units[line] += 1
                    remaining -= 1
                    progressed = True
            if not progressed:
                break
        for line in eligible:
            amounts[line] = currency.round(units[line] * rounding)
        return amounts

    def _get_deductible_line_percents(self):
        """{line: exact discount %}: the bill's % on every line, or in fixed
        mode `amount / gross * 100` (same formula as `discount_fixed`) with the
        amounts of `_get_deductible_line_amounts`."""
        self.ensure_one()
        lines = self._get_deductible_product_lines()
        percents = dict.fromkeys(lines, 0.0)
        if not self.is_deductible or not lines:
            return percents
        if self.global_deductible_type == "percent":
            if 0.0 < self.global_deductible_percent < 100.0:
                percents = dict.fromkeys(lines, self.global_deductible_percent)
            return percents
        for line, amount in self._get_deductible_line_amounts().items():
            gross = line.price_unit * line.quantity
            if amount and gross:
                percents[line] = (amount / gross) * 100.0
        return percents

    def _get_deductible_exempt_taxes(self):
        company = self.company_id
        return (
            company.exent_aliquot_purchase | company.exent_aliquot_purchase_international
        )

    def _is_deductible_exempt_tax(self, tax):
        """Exempt = the company's purchase exempt tax or a 0% tax."""
        if tax in self._get_deductible_exempt_taxes():
            return True
        return all(
            t.amount_type == "percent" and float_is_zero(t.amount, precision_digits=6)
            for t in tax.flatten_taxes_hierarchy()
        )

    def _get_deductible_issues(self):
        """Reasons why this bill cannot be deductible (list of messages)."""
        self.ensure_one()
        issues = []
        for line in self._get_deductible_product_lines():
            name = line.product_id.display_name or line.name or ""
            if not line.tax_ids or not all(
                self._is_deductible_exempt_tax(t) for t in line.tax_ids
            ):
                issues.append(
                    _("%s: every line must have an exempt tax.", name)
                )
            if line.discount or line.discount_fixed:
                issues.append(
                    _("%s: lines cannot have a previous discount.", name)
                )
        return issues

    @api.depends(
        "is_deductible",
        "global_deductible_type",
        "global_deductible_percent",
        "global_deductible_amount",
        "invoice_line_ids.price_unit",
        "invoice_line_ids.quantity",
        "invoice_line_ids.display_type",
    )
    def _compute_deductible_reference_amount(self):
        for move in self:
            amount = 0.0
            if move.is_deductible and move.currency_id:
                if move.global_deductible_type == "percent":
                    amount = move._get_deductible_gross_total() * (
                        move.global_deductible_percent / 100.0
                    )
                else:
                    amount = move.global_deductible_amount
            move.global_deductible_reference_amount = (
                move.currency_id.round(amount) if move.currency_id else amount
            )

    @api.onchange("is_deductible")
    def _onchange_is_deductible(self):
        for move in self:
            if not move.is_deductible:
                move.global_deductible_percent = 0.0
                move.global_deductible_amount = 0.0
                continue
            issues = move._get_deductible_issues()
            if issues:
                move.is_deductible = False
                return {
                    "warning": {
                        "title": _("Deductible cannot be enabled"),
                        "message": "\n".join(issues),
                    }
                }

    @api.onchange(
        "is_deductible",
        "global_deductible_type",
        "global_deductible_percent",
        "global_deductible_amount",
        "invoice_line_ids",
    )
    def _onchange_deductible_lines(self):
        """Keep every line consistent on the fly: assign the per-line amount
        and percent explicitly, as a change of the native `discount` does, so
        each line refreshes its own subtotal in the form."""
        for move in self:
            percents = move._get_deductible_line_percents()
            amounts = (
                move._get_deductible_line_amounts()
                if move.is_deductible and move.global_deductible_type == "amount"
                else {}
            )
            for line in move._get_deductible_product_lines():
                line.global_deductible_line_amount = amounts.get(line, 0.0)
                line.global_deductible_discount_percent = percents.get(line, 0.0)

    @api.onchange("global_deductible_type")
    def _onchange_deductible_type(self):
        for move in self:
            move.global_deductible_percent = 0.0
            move.global_deductible_amount = 0.0

    @api.onchange("invoice_line_ids")
    def _onchange_invoice_line_ids_deductible(self):
        for move in self:
            if move.is_deductible:
                issues = move._get_deductible_issues()
                if issues:
                    return {
                        "warning": {
                            "title": _("Invalid lines for a deductible bill"),
                            "message": "\n".join(issues),
                        }
                    }

    @api.constrains(
        "is_deductible",
        "global_deductible_type",
        "global_deductible_percent",
        "global_deductible_amount",
        "move_type",
        "reversed_entry_id",
        "invoice_line_ids",
    )
    def _check_deductible(self):
        """Vendor bills (or credit notes of a deductible bill), exempt taxes,
        no previous discount, value limits and per-line amounts adding up to
        the amount entered."""
        for move in self.filtered("is_deductible"):
            if move.move_type == "in_refund" and move.reversed_entry_id.is_deductible:
                pass
            elif move.move_type != "in_invoice":
                raise ValidationError(
                    _("The deductible can only be used on vendor bills.")
                )
            elif not move.company_id.use_deductible:
                raise ValidationError(
                    _("The deductible is not enabled for this company. Enable it "
                      "in the accounting settings.")
                )
            issues = move._get_deductible_issues()
            if issues:
                raise ValidationError(
                    _("The deductible cannot be applied:\n%s", "\n".join(issues))
                )
            if move.global_deductible_type == "percent":
                if not 0.0 < move.global_deductible_percent < 100.0:
                    raise ValidationError(
                        _("The deductible percentage must be greater than 0 and "
                          "less than 100: 100% of a bill cannot be deducted.")
                    )
            else:
                gross = move._get_deductible_gross_total()
                precision = move.currency_id.decimal_places
                if float_compare(
                    move.global_deductible_amount, 0.0, precision_digits=precision
                ) <= 0 or float_compare(
                    move.global_deductible_amount, gross, precision_digits=precision
                ) >= 0:
                    raise ValidationError(
                        _("The deductible amount must be greater than 0 and "
                          "less than the original bill total (%s): 100%% of a "
                          "bill cannot be deducted.",
                          formatLang(self.env, gross, currency_obj=move.currency_id))
                    )
                distributed = sum(
                    move._get_deductible_product_lines().mapped(
                        "global_deductible_line_amount"
                    )
                )
                if float_compare(
                    distributed,
                    move.global_deductible_amount,
                    precision_rounding=move.currency_id.rounding,
                ) != 0:
                    raise ValidationError(
                        _(
                            "The amounts deducted on the lines (%(lines)s) must add "
                            "up to the deductible amount (%(total)s).",
                            lines=distributed,
                            total=move.global_deductible_amount,
                        )
                    )

    @api.depends("invoice_line_ids.global_deductible_discount_percent")
    def _compute_company_currency_line_totals(self):
        """Patch the entries of deductible lines: the base computation only
        knows the (zero) native discount."""
        super()._compute_company_currency_line_totals()
        precision = self.env["decimal.precision"].precision_get("Product Price")
        for move in self.filtered("is_deductible"):
            totals = move.company_currency_line_totals or {}
            cc = move.company_currency_id
            for line in move.line_ids.filtered(lambda l: l._uses_deductible_discount()):
                entry = totals.get(str(line.id))
                if not entry:
                    continue
                denominator = line.quantity * (
                    1 - line.global_deductible_discount_percent / 100.0
                )
                price_unit = (
                    float_round(entry["subtotal"] / denominator, precision_digits=precision)
                    if not float_is_zero(denominator, precision_digits=precision)
                    else 0.0
                )
                entry["price_unit"] = price_unit
                entry["discount_amount"] = cc.round(
                    price_unit * line.quantity - entry["subtotal"]
                )
                entry["discount_type"] = (
                    "percent" if move.global_deductible_type == "percent" else "amount"
                )
            move.company_currency_line_totals = totals

    @api.depends(
        "is_deductible",
        "global_deductible_type",
        "global_deductible_percent",
        "global_deductible_amount",
        "invoice_line_ids.global_deductible_discount_percent",
        "invoice_line_ids.foreign_subtotal",
    )
    def _compute_tax_totals(self):
        """Add to `tax_totals` the subtotal without deductible and the
        deductible in the three currencies of the widgets. The deductible is
        converted exactly, so original - deductible == the booked subtotal."""
        super()._compute_tax_totals()
        for move in self:
            totals = move.tax_totals
            if not totals or not move.is_deductible or move.move_type not in (
                "in_invoice",
                "in_refund",
            ):
                continue
            product_lines = move._get_deductible_product_lines()
            currency = move.currency_id
            foreign = move.foreign_currency_id
            ves = move.company_id.currency_id

            deducted = move.global_deductible_reference_amount
            original = totals.get("base_amount_currency", 0.0) + deducted

            first_line = product_lines[:1]
            rate = first_line.currency_rate or 1.0
            deducted_ves = ves.round(deducted / rate)
            original_ves = totals.get("base_amount", 0.0) + deducted_ves

            deducted_foreign = 0.0
            if foreign and first_line:
                deducted_foreign = foreign.round(
                    currency._convert(
                        deducted,
                        foreign,
                        move.company_id,
                        first_line._get_foreign_rate_date(),
                        round=False,
                    )
                )
            original_foreign = (
                totals.get("base_amount_foreign_currency", 0.0) + deducted_foreign
            )

            def fmt(value, curr):
                return formatLang(self.env, value, currency_obj=curr)

            totals.update(
                {
                    "is_deductible": True,
                    "formatted_deductible_original_currency": fmt(original, currency),
                    "formatted_deductible_amount_currency": fmt(deducted, currency),
                    "formatted_deductible_original_foreign": fmt(original_foreign, foreign),
                    "formatted_deductible_amount_foreign": fmt(deducted_foreign, foreign),
                    "formatted_deductible_original_ves": fmt(original_ves, ves),
                    "formatted_deductible_amount_ves": fmt(deducted_ves, ves),
                }
            )
            move.tax_totals = totals

    @api.depends("invoice_line_ids", "tax_totals")
    def _compute_detailed_amounts(self):
        """The base method reads the native `discount`; the deductible lives in
        its own field, so gross / discount / net would not add up."""
        super()._compute_detailed_amounts()
        for move in self.filtered("is_deductible"):
            details = dict(move.detailed_amounts or {})
            if not details:
                continue
            lines = move._get_deductible_product_lines()
            gross = sum(l.price_unit * l.quantity for l in lines)
            discount = gross - sum(lines.mapped("price_subtotal"))

            def fmt(value, move=move):
                return formatLang(self.env, value, currency_obj=move.currency_id)

            details.update(
                {
                    "gross_amount": gross,
                    "formatted_gross_amount": fmt(gross),
                    "discount_amount": discount,
                    "formatted_discount_amount": fmt(discount),
                    "gross_discount_amount": gross,
                    "formatted_gross_discount_amount": fmt(gross - discount),
                }
            )
            move.detailed_amounts = details
