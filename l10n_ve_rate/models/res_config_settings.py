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

    foreign_currency_id = fields.Many2one(
        "res.currency",
        string="Currency Foreign",
        help="Currency Foreign for the company",
        related="company_id.foreign_currency_id",
        readonly=False,
    )