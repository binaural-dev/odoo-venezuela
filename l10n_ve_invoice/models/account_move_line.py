from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.float_utils import float_compare, float_is_zero


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    discount_fixed = fields.Float(
        string="Discount (Fixed)",
        digits="Product Price",
        default=0.0,
        help="Fixed amount discount on the line's gross subtotal (price_unit "
        "* quantity), subtracted before taxes. Used instead of Discount (%) "
        "when the company's Invoice Line Discount Type is set to Fixed "
        "Amount. Applies on create/write, not only through the form.",
    )

    @api.model
    def _enforce_discount_exclusivity(self, vals, company=None):
        """Only one of discount (%) / discount_fixed is ever meaningful on a
        line: the company's discount_type says which. Whenever a write
        touches either field, the OTHER one is forced to 0 right there --
        no comparison against prior values needed, the config alone decides.
        """
        if "discount" not in vals and "discount_fixed" not in vals:
            return
        company = company or (
            self.env["res.company"].browse(vals["company_id"])
            if vals.get("company_id")
            else (self.company_id or self.env.company)
        )
        if company.discount_type == "amount":
            vals["discount"] = 0.0
        else:
            vals["discount_fixed"] = 0.0

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._enforce_discount_exclusivity(vals)
        return super().create(vals_list)

    def write(self, vals):
        if "discount" in vals or "discount_fixed" in vals:
            for line in self:
                line_vals = dict(vals)
                self._enforce_discount_exclusivity(line_vals, company=line.company_id)
                super(AccountMoveLine, line).write(line_vals)
            return True
        return super().write(vals)

    @api.onchange("discount", "discount_fixed")
    def _onchange_discount_exclusivity(self):
        """Form-side mirror of _enforce_discount_exclusivity: the field the
        company's discount_type doesn't use is always zero, on the spot."""
        for line in self:
            if line.company_id.discount_type == "amount":
                line.discount = 0.0
            else:
                line.discount_fixed = 0.0

    def _uses_discount_fixed(self):
        """Whether this line's totals must be derived from discount_fixed
        instead of the native discount (%)."""
        self.ensure_one()
        precision = self.env["decimal.precision"].precision_get("Product Price")
        return self.company_id.discount_type == "amount" and not float_is_zero(
            self.discount_fixed, precision_digits=precision
        )

    def _get_exact_discount_percentage(self):
        """% equivalent to discount_fixed over the line's gross subtotal,
        WITHOUT rounding to the "Discount" precision (2 decimals): rounding
        it there is what causes the Base Imponible to drift from the fixed
        amount the user configured. This value is only ever used to feed
        the tax computation directly (see AccountTax._prepare_base_line_for
        _taxes_computation and _compute_foreign_subtotal below) -- it is
        never written to the stored discount field.
        """
        self.ensure_one()
        precision = self.env["decimal.precision"].precision_get("Product Price")
        gross_subtotal = self.price_unit * self.quantity
        if float_is_zero(gross_subtotal, precision_digits=precision) or float_is_zero(
            self.discount_fixed, precision_digits=precision
        ):
            return 0.0
        return (self.discount_fixed / gross_subtotal) * 100.0

    @api.constrains("discount_fixed", "price_unit", "quantity")
    def _check_discount_fixed_not_exceeding_subtotal(self):
        precision = self.env["decimal.precision"].precision_get("Product Price")
        for line in self:
            if line.company_id.discount_type != "amount" or not line.product_id:
                continue
            gross_subtotal = line.price_unit * line.quantity
            if (
                float_compare(
                    line.discount_fixed, gross_subtotal, precision_digits=precision
                )
                >= 0
            ):
                raise ValidationError(
                    _(
                        "Fixed discount (%(discount)s) on %(product)s must be "
                        "less than its subtotal (%(subtotal)s).",
                        product=line.product_id.display_name,
                        discount=line.discount_fixed,
                        subtotal=gross_subtotal,
                    )
                )

    @api.depends("discount_fixed")
    def _compute_totals(self):
        return super()._compute_totals()

    @api.depends("discount_fixed")
    def _compute_foreign_subtotal(self):
        """l10n_ve_accountant's _compute_foreign_subtotal derives the
        foreign-currency amounts from the stored `discount` (%), same
        precision problem as the native price_subtotal/price_total. Reuse
        the exact ratio here too, or the alternate-currency amounts would
        drift out of sync with the (now exact) native ones.
        """
        fixed_lines = self.filtered(lambda l: l._uses_discount_fixed())
        for line in fixed_lines:
            exact_discount = line._get_exact_discount_percentage()
            line_discount_price_unit = line.foreign_price * (
                1 - (exact_discount / 100.0)
            )
            foreign_subtotal = line_discount_price_unit * line.quantity

            if line.tax_ids:
                taxes_res = line.tax_ids.compute_all(
                    line_discount_price_unit,
                    quantity=line.quantity,
                    currency=line.foreign_currency_id,
                    product=line.product_id,
                    partner=line.partner_id,
                    is_refund=line.is_refund,
                )
                line.foreign_subtotal = taxes_res["total_excluded"]
                line.foreign_price_total = taxes_res["total_included"]
            else:
                line.foreign_price_total = line.foreign_subtotal = foreign_subtotal

        return super(AccountMoveLine, self - fixed_lines)._compute_foreign_subtotal()

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
