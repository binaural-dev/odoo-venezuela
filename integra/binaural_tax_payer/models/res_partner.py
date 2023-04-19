from odoo import models, fields


class ResPartner(models.Model):
    _inherit = "res.partner"

    taxpayer_type = fields.Selection(
        [
            ("formal", "Formal"),
            ("special", "Special"),
            ("ordinary", "Ordinary"),
        ],
        default="ordinary",
        store=True,
    )