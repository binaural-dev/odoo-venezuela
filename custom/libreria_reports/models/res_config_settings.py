from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    store_location_id = fields.Many2one(
        "stock.location", related="company_id.store_location_id", readonly=False
    )
