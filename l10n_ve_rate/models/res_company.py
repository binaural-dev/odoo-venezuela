from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

import logging

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):
    _inherit = "res.company"

    foreign_currency_id = fields.Many2one(
        "res.currency",
        string="Foreign Currency",
        help="Foreign Currency for the company"
    )

    def write(self, vals):
        before_currency = self.foreign_currency_id
        res = super().write(vals)
        if "foreign_currency_id" in vals and before_currency:
            lines = self.env["account.move.line"].search(
                [("foreign_currency_id", "=", before_currency.id)]
            )
            if lines:
                raise ValidationError(
                    _(
                        "The currency already has accounting movements, you cannot deactivate this foreign currency"
                    )
                )
        return res
