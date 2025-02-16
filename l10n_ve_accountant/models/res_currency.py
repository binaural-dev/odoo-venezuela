from odoo import models, _
from odoo.exceptions import ValidationError


class ResCurrency(models.Model):
    _inherit = "res.currency"

    def write(self, vals):
        res = super().write(vals)
        if "active" in vals and not vals["active"]:
            company_id = self.env.company
            if self.id == company_id.currency_foreign_id.id or self.id == company_id.currency_id.id:
                lines = self.env["account.move.line"].search(
                    ["|", ("foreign_currency_id", "=", self.id), ("currency_id", "=", self.id)]
                )
                if lines:
                    raise ValidationError(
                        _(
                            "The currency already has accounting movements, you cannot deactivate this currency"
                        )
                    )
        return res
