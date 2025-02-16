from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

import logging

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):
    _inherit = "res.company"

    currency_foreign_id = fields.Many2one(
        "res.currency", string="Currency Foreign", help="Currency Foreign for the company"
    )

    def write(self, vals):
        before_currency = self.currency_foreign_id
        res = super().write(vals)
        # if "currency_foreign_id" in vals and before_currency:
        #     lines = self.env["account.move.line"].search([("currency_foreign_id", "=", before_currency.id)], limit=1)
        #     if lines:
        #         raise ValidationError(
        #             _("The currency already has accounting movements, you cannot deactivate this foreign currency")
        #         )
        return res
