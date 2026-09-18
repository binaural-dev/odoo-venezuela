from odoo import api, fields, models
from odoo.tools.float_utils import float_is_zero, float_round


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    discount_fixed = fields.Float(
        string="Discount (Fixed)",
        digits="Product Price",
        default=0.0,
        help="Fixed amount discount on the line's gross subtotal (price_unit "
        "* quantity). Converted to the equivalent Discount (%) so taxes, "
        "totals and foreign amounts keep working as usual.",
    )

    def _get_discount_percentage_from_fixed(self, discount_fixed, price_unit, quantity):
        """% equivalent to a fixed discount over the line's gross subtotal.

        discount_fixed is subtracted from price_unit * quantity (the whole
        line), not from price_unit alone, so it matches the % discount's own
        semantics (which already scales with quantity).
        """
        precision = self.env["decimal.precision"].precision_get("Product Price")
        gross_subtotal = price_unit * quantity
        if float_is_zero(gross_subtotal, precision_digits=precision) or float_is_zero(
            discount_fixed, precision_digits=precision
        ):
            return 0.0
        return float_round(
            (discount_fixed / gross_subtotal) * 100.0,
            precision_digits=self.env["decimal.precision"].precision_get(
                "Discount"
            ),
        )

    @api.onchange("discount_fixed", "price_unit", "quantity")
    def _onchange_discount_fixed(self):
        """UI-only: discount_fixed -> native discount (%).

        No create()/write() override on purpose: code writes to
        discount_fixed do not touch discount, same as native Odoo.
        """
        if self.env.context.get("ignore_discount_fixed_onchange"):
            return
        for line in self.with_context(ignore_discount_fixed_onchange=True):
            line.discount = line._get_discount_percentage_from_fixed(
                line.discount_fixed, line.price_unit, line.quantity
            )

    @api.constrains("product_id", "price_unit", "quantity", "discount")
    def _check_refund_line_against_origin(self):
        """A write() on the line itself does not trigger the parent
        account.move constrains on invoice_line_ids, so the same check
        (see account.move._check_refund_against_origin) is repeated here.
        """
        moves = self.mapped("move_id").filtered(
            lambda m: m.move_type in ("out_refund", "in_refund") and m.reversed_entry_id
        )
        if moves:
            moves._check_refund_against_origin()
