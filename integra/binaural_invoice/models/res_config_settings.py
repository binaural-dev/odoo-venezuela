from odoo import api, fields, models, _


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    max_product_invoice = fields.Integer(
        related="company_id.max_product_invoice",
        readonly=False,
    )
