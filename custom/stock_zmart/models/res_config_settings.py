from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    warehouse_operator_ids = fields.One2many(
        related="company_id.warehouse_operator_ids", readonly=False
    )
