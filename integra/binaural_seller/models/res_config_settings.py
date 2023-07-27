from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )

    initial_seller = fields.Many2one(
                                string='Default seller when creating contact',
                                related='company_id.initial_seller',
                                readonly=False,
                            )
