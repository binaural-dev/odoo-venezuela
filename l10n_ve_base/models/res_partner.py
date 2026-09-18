from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    tz = fields.Selection(
        default=lambda self: self.env.context.get("tz") or "America/Caracas",
    )
