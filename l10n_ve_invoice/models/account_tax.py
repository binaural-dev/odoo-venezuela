from odoo import models


class AccountTax(models.Model):
    _inherit = "account.tax"

    def _prepare_base_line_for_taxes_computation(self, record, **kwargs):
        res = super()._prepare_base_line_for_taxes_computation(record, **kwargs)
        # record._uses_discount_fixed() is False unless discount_fixed is
        # actually set on this line, so this never touches EPD/down-payment/
        # cash-rounding synthetic lines (discount_fixed defaults to 0 there).
        if (
            record
            and not isinstance(record, dict)
            and record._name == "account.move.line"
            and record._uses_discount_fixed()
        ):
            res["discount"] = record._get_exact_discount_percentage()
        return res
