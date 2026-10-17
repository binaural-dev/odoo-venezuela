from odoo import models


class AccountTax(models.Model):
    _inherit = "account.tax"

    def _prepare_base_line_for_taxes_computation(self, record, **kwargs):
        """Feed the deductible percent of the line as its discount; it is only
        set on lines of deductible bills, so synthetic lines are untouched."""
        res = super()._prepare_base_line_for_taxes_computation(record, **kwargs)
        if (
            record
            and not isinstance(record, dict)
            and record._name == "account.move.line"
            and record._uses_deductible_discount()
        ):
            res["discount"] = record.global_deductible_discount_percent
        return res
