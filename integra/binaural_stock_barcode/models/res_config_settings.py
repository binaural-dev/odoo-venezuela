from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    restrict_add_exceeding_quantity = fields.Boolean(
        related="company_id.restrict_add_exceeding_quantity",
        readonly=False,
    )
