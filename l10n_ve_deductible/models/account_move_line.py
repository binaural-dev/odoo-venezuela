from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.float_utils import float_compare, float_is_zero


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    global_deductible_line_amount = fields.Monetary(
        string="Deductible Amount (line)",
        currency_field="currency_id",
        compute="_compute_deductible_line_amount",
        store=True,
        help="Share of the fixed deductible amount of the bill that is taken "
        "off this line, in the document currency: proportional to its gross "
        "subtotal, with the cents lost to rounding given back by largest "
        "remainder, so the lines always add up to the amount entered on the "
        "bill. Only used when the deductible is a fixed amount; read only.",
    )
    global_deductible_discount_percent = fields.Float(
        string="Deductible Discount (%)",
        compute="_compute_deductible_discount_percent",
        store=True,
        help="Exact percentage of the line's gross subtotal removed by the "
        "deductible of the bill. Deliberately NOT rounded (no digits): any "
        "rounding changes the cent of the line subtotal, so the result would "
        "no longer match the native discount / discount_fixed.",
    )

    @api.depends(
        "display_type",
        "price_unit",
        "quantity",
        "move_id.is_deductible",
        "move_id.global_deductible_type",
        "move_id.global_deductible_amount",
        "move_id.invoice_line_ids.price_unit",
        "move_id.invoice_line_ids.quantity",
        "move_id.invoice_line_ids.display_type",
    )
    def _compute_deductible_line_amount(self):
        amounts_by_move = {}
        for line in self:
            move = line.move_id
            amount = 0.0
            if (
                move.is_deductible
                and move.global_deductible_type == "amount"
                and line.display_type == "product"
            ):
                if move not in amounts_by_move:
                    amounts_by_move[move] = move._get_deductible_line_amounts()
                amount = amounts_by_move[move].get(line, 0.0)
            line.global_deductible_line_amount = amount

    @api.depends(
        "display_type",
        "price_unit",
        "quantity",
        "move_id.is_deductible",
        "move_id.global_deductible_type",
        "move_id.global_deductible_percent",
        "move_id.global_deductible_amount",
        "move_id.invoice_line_ids.price_unit",
        "move_id.invoice_line_ids.quantity",
        "move_id.invoice_line_ids.display_type",
    )
    def _compute_deductible_discount_percent(self):
        """Same distribution as `global_deductible_line_amount`: the percent
        is computed from the bill (not read from the stored amount) so the
        totals refresh live while the form is edited."""
        percents_by_move = {}
        for line in self:
            move = line.move_id
            percent = 0.0
            if move.is_deductible and line.display_type == "product":
                if move not in percents_by_move:
                    percents_by_move[move] = move._get_deductible_line_percents()
                percent = percents_by_move[move].get(line, 0.0)
            line.global_deductible_discount_percent = percent

    def _get_effective_discount_percent(self):
        if self._uses_deductible_discount():
            return self.global_deductible_discount_percent
        return super()._get_effective_discount_percent()

    def _uses_deductible_discount(self):
        self.ensure_one()
        return self.display_type == "product" and not float_is_zero(
            self.global_deductible_discount_percent, precision_digits=10
        )

    @api.depends("global_deductible_discount_percent")
    def _compute_totals(self):
        return super()._compute_totals()

    @api.depends("global_deductible_discount_percent")
    def _compute_foreign_subtotal(self):
        """The base computation derives the alternate-currency amounts from
        the stored `discount`; deductible lines need the exact percent."""
        deductible_lines = self.filtered(lambda l: l._uses_deductible_discount())
        for line in deductible_lines:
            discounted_price = line.foreign_price * (
                1 - line.global_deductible_discount_percent / 100.0
            )
            if line.tax_ids:
                taxes_res = line.tax_ids.compute_all(
                    discounted_price,
                    quantity=line.quantity,
                    currency=line.foreign_currency_id,
                    product=line.product_id,
                    partner=line.partner_id,
                    is_refund=line.is_refund,
                )
                line.foreign_subtotal = taxes_res["total_excluded"]
                line.foreign_price_total = taxes_res["total_included"]
            else:
                line.foreign_subtotal = discounted_price * line.quantity
                line.foreign_price_total = line.foreign_subtotal
        return super(AccountMoveLine, self - deductible_lines)._compute_foreign_subtotal()

    @api.constrains("discount", "discount_fixed", "move_id")
    def _check_no_previous_discount_on_deductible(self):
        for line in self:
            if (
                line.move_id.is_deductible
                and line.display_type == "product"
                and (line.discount or line.discount_fixed)
            ):
                raise ValidationError(
                    _(
                        "A deductible bill cannot have lines with a discount "
                        "(percentage or fixed amount). Remove the discount on "
                        "%(product)s.",
                        product=line.product_id.display_name or line.name,
                    )
                )

    @api.constrains(
        "price_unit",
        "quantity",
        "tax_ids",
        "display_type",
        "move_id",
        "global_deductible_line_amount",
    )
    def _check_deductible_move(self):
        """`account.move._check_deductible` cannot listen to the lines'
        fields (constrains ignores dotted paths), so it is triggered here,
        together with the per-line limit of the fixed amount."""
        for line in self.filtered(
            lambda l: l.move_id.is_deductible
            and l.move_id.global_deductible_type == "amount"
            and l.display_type == "product"
        ):
            gross = line.price_unit * line.quantity
            if gross > 0 and float_compare(
                line.global_deductible_line_amount,
                gross,
                precision_rounding=line.currency_id.rounding,
            ) >= 0:
                raise ValidationError(
                    _(
                        "The deductible taken off %(product)s must be less than "
                        "its subtotal (%(subtotal)s).",
                        product=line.product_id.display_name or line.name,
                        subtotal=gross,
                    )
                )
        self.move_id.filtered("is_deductible")._check_deductible()
