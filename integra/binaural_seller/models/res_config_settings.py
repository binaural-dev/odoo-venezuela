from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    initial_seller = fields.Many2one(
        string="Default seller when creating contact",
        related="company_id.initial_seller",
        readonly=False,
    )

    multiple_sellers = fields.Boolean(
        related='company_id.multiple_sellers',
        readonly=False
    )

    restrict_seller = fields.Boolean(
        related='company_id.restrict_seller',
        readonly=False
    )

    company_seller = fields.Boolean(
        related='company_id.company_seller',
        readonly=False
    )
