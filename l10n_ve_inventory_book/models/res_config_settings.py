from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    display_consumables = fields.Boolean(
        "Display Consumables in Inventory Book",
        related="company_id.display_consumables",
        readonly=False,
    )