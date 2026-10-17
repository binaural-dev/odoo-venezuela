from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import float_compare, formatLang


class AccountMoveLine(models.Model):
    """Per-line figures of the deductible. The percent is what the tax
    computation reads as the line discount (see `_get_effective_discount_percent`)."""

    _inherit = "account.move.line"

    global_deductible_line_amount = fields.Monetary(
        string="Deductible Amount (line)",
        currency_field="currency_id",
        compute="_compute_deductible_line_amount",
        store=True,
        help="Share of the fixed deductible amount of the document that is taken "
        "off this line, in the document currency: proportional to its gross "
        "subtotal, with the cents lost to rounding given back by largest "
        "remainder, so the lines always add up to the amount entered on the "
        "document. Only used when the deductible is a fixed amount; read only.",
    )
    global_deductible_discount_percent = fields.Float(
        string="Deductible Discount (%)",
        compute="_compute_deductible_discount_percent",
        store=True,
        help="Exact percentage of the line's gross subtotal removed by the "
        "deductible of the document. Deliberately NOT rounded (no digits): any "
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
        "move_id.currency_id",
        "move_id.invoice_line_ids.price_unit",
        "move_id.invoice_line_ids.quantity",
        "move_id.invoice_line_ids.display_type",
    )
    def _compute_deductible_line_amount(self):
        amounts = {move: move._get_deductible_line_amounts() for move in self.move_id}
        for line in self:
            line.global_deductible_line_amount = amounts.get(line.move_id, {}).get(line, 0.0)

    @api.depends(
        "display_type",
        "price_unit",
        "quantity",
        "move_id.is_deductible",
        "move_id.global_deductible_type",
        "move_id.global_deductible_percent",
        "move_id.global_deductible_amount",
        "move_id.currency_id",
        "move_id.invoice_line_ids.price_unit",
        "move_id.invoice_line_ids.quantity",
        "move_id.invoice_line_ids.display_type",
    )
    def _compute_deductible_discount_percent(self):
        """Computed from the document (not read from the stored amount) so the
        totals refresh live while the form is edited."""
        percents = {move: move._get_deductible_line_percents() for move in self.move_id}
        for line in self:
            line.global_deductible_discount_percent = percents.get(line.move_id, {}).get(line, 0.0)

    def _get_effective_discount_percent(self):
        return self.global_deductible_discount_percent or super()._get_effective_discount_percent()

    @api.depends("global_deductible_discount_percent")
    def _compute_totals(self):
        return super()._compute_totals()

    @api.depends("global_deductible_discount_percent")
    def _compute_foreign_subtotal(self):
        return super()._compute_foreign_subtotal()

    @api.constrains("discount", "discount_fixed", "move_id")
    def _check_no_previous_discount_on_deductible(self):
        for line in self.filtered(lambda line: line.move_id.is_deductible and line.display_type == "product"):
            if line.discount or line.discount_fixed:
                raise ValidationError(
                    _(
                        "A deductible document cannot have lines with a discount "
                        "(percentage or fixed amount). Remove the discount on "
                        "%(product)s.",
                        product=line.product_id.display_name or line.name,
                    )
                )

    @api.constrains(
        "price_unit", "quantity", "tax_ids", "display_type", "move_id", "global_deductible_line_amount"
    )
    def _check_deductible_move(self):
        """`account.move._check_deductible` cannot listen to the lines'
        fields (constrains ignores dotted paths), so it is triggered here,
        together with the per-line limit of the fixed amount."""
        for line in self.filtered("global_deductible_line_amount"):
            gross = line.price_unit * line.quantity
            if gross > 0 and float_compare(
                line.global_deductible_line_amount, gross, precision_rounding=line.currency_id.rounding
            ) >= 0:
                raise ValidationError(
                    _(
                        "The deductible taken off %(product)s must be less than "
                        "its subtotal (%(subtotal)s).",
                        product=line.product_id.display_name or line.name,
                        subtotal=formatLang(self.env, gross, currency_obj=line.currency_id),
                    )
                )
        self.move_id.filtered("is_deductible")._check_deductible()
