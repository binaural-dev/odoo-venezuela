from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class ResCompany(models.Model):
    _inherit = "res.company"

    taxpayer_type = fields.Selection(
        [
            ("formal", "Formal"),
            ("special", "Special"),
            ("ordinary", "Ordinary"),
        ],
        default="special",
        tracking=True,
    )

    vat = fields.Char(
        string="RIF",
        tracking=True,
    )

    street = fields.Char(tracking=True)

    country_id = fields.Many2one(
        tracking=True,
        default=lambda self: self.env["res.country"].search([("code", "=", "VE")], limit=1),
    )
