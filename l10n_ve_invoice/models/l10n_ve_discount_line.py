from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.float_utils import float_compare, float_is_zero


class DiscountLineMixin(models.AbstractModel):
    """Fixed amount discount of a document line, shared by invoice lines and
    sale order lines.

    Only one of discount (%) / discount_fixed is ever meaningful on a line.
    `_get_line_discount_type` says which (the company setting by default, the
    document's scheme where a module chooses it per document). The fixed
    amount feeds the tax computation through its exact % equivalent: it is
    never written to the stored discount field.
    """

    _name = "l10n_ve.discount.line.mixin"
    _description = "Line fixed amount discount"

    discount_fixed = fields.Float(
        string="Discount (Fixed)",
        digits="Product Price",
        default=0.0,
        help="Fixed amount discount on the line's gross subtotal (price_unit "
        "* quantity), subtracted before taxes. Used instead of Discount (%) "
        "when the line uses fixed amount discounts. Applies on create/write, "
        "not only through the form.",
    )

    def _discount_quantity(self):
        """Quantity the unit price is multiplied by (the field differs by model)."""
        raise NotImplementedError

    def _get_discount_gross(self):
        """price_unit * quantity: the amount a discount of the line applies to."""
        self.ensure_one()
        return self.price_unit * self._discount_quantity()

    def _get_line_discount_type(self, company=None, vals=None):
        """Which discount ('percent' or 'amount') this line uses. By default
        the company setting decides; modules that choose it per document
        override this single hook (the exclusivity, the exact percentage and
        the constraint below all read it). `vals` are the values being
        written when the line does not exist yet."""
        company = company or self.company_id or self.env.company
        return company.discount_type

    @api.model
    def _enforce_discount_exclusivity(self, vals, company=None):
        """Whenever a write touches either discount field, the OTHER one is
        forced to 0 right there -- no comparison against prior values needed,
        the discount type alone decides."""
        if "discount" not in vals and "discount_fixed" not in vals:
            return
        company = company or (
            self.env["res.company"].browse(vals["company_id"])
            if vals.get("company_id")
            else (self.company_id or self.env.company)
        )
        if self._get_line_discount_type(company=company, vals=vals) == "amount":
            vals["discount"] = 0.0
        else:
            vals["discount_fixed"] = 0.0

    @api.onchange("discount", "discount_fixed")
    def _onchange_discount_exclusivity(self):
        """Form-side mirror of _enforce_discount_exclusivity."""
        for line in self:
            if line._get_line_discount_type() == "amount":
                line.discount = 0.0
            else:
                line.discount_fixed = 0.0

    def _uses_discount_fixed(self):
        """Whether this line's totals must be derived from discount_fixed
        instead of the native discount (%)."""
        self.ensure_one()
        precision = self.env["decimal.precision"].precision_get("Product Price")
        return self._get_line_discount_type() == "amount" and not float_is_zero(
            self.discount_fixed, precision_digits=precision
        )

    def _get_exact_discount_percentage(self):
        """% equivalent to discount_fixed over the line's gross subtotal,
        WITHOUT rounding to the "Discount" precision (2 decimals): rounding
        it there is what makes the taxable base drift from the fixed amount
        the user configured."""
        self.ensure_one()
        precision = self.env["decimal.precision"].precision_get("Product Price")
        gross = self._get_discount_gross()
        if float_is_zero(gross, precision_digits=precision) or float_is_zero(
            self.discount_fixed, precision_digits=precision
        ):
            return 0.0
        return (self.discount_fixed / gross) * 100.0

    @api.constrains("discount_fixed", "price_unit")
    def _check_discount_fixed_not_exceeding_subtotal(self):
        precision = self.env["decimal.precision"].precision_get("Product Price")
        for line in self:
            if (
                not line.product_id
                or (line.display_type and line.display_type != "product")
                or float_is_zero(line.discount_fixed, precision_digits=precision)
            ):
                continue
            gross = line._get_discount_gross()
            if float_compare(line.discount_fixed, gross, precision_digits=precision) >= 0:
                raise ValidationError(
                    _(
                        "Fixed discount (%(discount)s) on %(product)s must be "
                        "less than its subtotal (%(subtotal)s).",
                        product=line.product_id.display_name,
                        discount=line.discount_fixed,
                        subtotal=gross,
                    )
                )
