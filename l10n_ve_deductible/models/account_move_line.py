from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
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
        readonly=False,
        help="Share of the fixed deductible amount of the document that is taken "
        "off this line, in the document currency. It is proposed proportional "
        "to the line's gross subtotal, with the cents lost to rounding given "
        "back by largest remainder, and can be edited by hand on a draft "
        "document; the lines must always add up to the amount entered on the "
        "document and none can reach its own subtotal. Only used when the "
        "deductible is a fixed amount.",
    )
    global_deductible_manual = fields.Boolean(
        string="Deductible Typed by Hand",
        copy=False,
        help="The amount of the deductible of this line was typed by the user: it is "
        "kept, and the rest of the amount of the document is spread over the other lines.",
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
        "global_deductible_manual",
        "move_id.is_deductible",
        "move_id.global_deductible_type",
        "move_id.global_deductible_amount",
        "move_id.currency_id",
        "move_id.invoice_line_ids.price_unit",
        "move_id.invoice_line_ids.quantity",
        "move_id.invoice_line_ids.display_type",
    )
    def _compute_deductible_line_amount(self):
        # In the form (virtual records) the onchange of the document assigns the
        # amounts: computing them here would change the amount of the line being
        # edited and the onchange of that field would take it as typed by the user.
        saved = self.filtered(lambda line: bool(line.id))
        amounts = {move: move._get_deductible_line_amounts() for move in saved.move_id}
        for line in saved:
            line.global_deductible_line_amount = amounts.get(line.move_id, {}).get(line, 0.0)
        for line in self - saved:
            line.global_deductible_line_amount = line.global_deductible_line_amount

    @api.depends(
        "display_type",
        "price_unit",
        "quantity",
        "global_deductible_line_amount",
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

    @api.onchange("global_deductible_line_amount")
    def _onchange_global_deductible_line_amount(self):
        """What the user types in the line is kept and the rest is spread again
        (by the onchange of the document). A new line starts with no amount
        (0.0): that is not something typed."""
        for line in self:
            line.global_deductible_manual = bool(line.global_deductible_line_amount)

    def write(self, vals):
        """The amount of a line can be typed by hand, only on a draft document."""
        if "global_deductible_line_amount" in vals:
            posted = self.move_id.filtered(lambda move: move.state != "draft")
            if posted:
                raise UserError(
                    _(
                        "The deductible can only be changed on draft documents. "
                        "Reset %s to draft first.",
                        ", ".join(posted.mapped("display_name")),
                    )
                )
        return super().write(vals)

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

    @api.constrains("price_unit", "quantity", "tax_ids", "display_type", "move_id")
    def _check_deductible_move(self):
        """`account.move._check_deductible` cannot listen to the lines'
        fields (constrains ignores dotted paths), so it is triggered here.
        The amounts typed in the lines are not added up here: the lines of a
        document are written one by one, so the sum is checked on the document
        (`invoice_line_ids` of the move) and when it is posted."""
        self.move_id.filtered("is_deductible")._check_deductible(check_sum=False)

    @api.constrains("global_deductible_line_amount")
    def _check_deductible_line_limit(self):
        """No line can take off its whole subtotal or more."""
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

    def _copy_data_extend_business_fields(self, values):
        """A credit or debit note keeps the amounts typed in the lines."""
        super()._copy_data_extend_business_fields(values)
        if self.global_deductible_manual:
            values["global_deductible_line_amount"] = self.global_deductible_line_amount
            values["global_deductible_manual"] = True
