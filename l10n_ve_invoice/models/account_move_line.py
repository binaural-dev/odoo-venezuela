from odoo import api, models


class AccountMoveLine(models.Model):
    _inherit = ["account.move.line", "l10n_ve.discount.line.mixin"]
    _name = "account.move.line"

    def _discount_quantity(self):
        return self.quantity

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

    def _get_effective_discount_percent(self):
        if self._uses_discount_fixed():
            return self._get_exact_discount_percentage()
        return super()._get_effective_discount_percent()

    @api.constrains("quantity")
    def _check_discount_fixed_quantity(self):
        self._check_discount_fixed_not_exceeding_subtotal()

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
