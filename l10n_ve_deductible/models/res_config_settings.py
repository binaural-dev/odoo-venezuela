from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    use_deductible = fields.Boolean(
        related="company_id.use_deductible", readonly=False
    )
    deductible_scope = fields.Selection(
        related="company_id.deductible_scope", readonly=False
    )
