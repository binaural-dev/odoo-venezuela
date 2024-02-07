from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    scan_barcode_scale_by_price = fields.Boolean(
        related="company_id.scan_barcode_scale_by_price", readonly=False
    )
    scan_barcode_scale_by_price_with_tax = fields.Boolean(
        related="company_id.scan_barcode_scale_by_price_with_tax", readonly=False
    )
