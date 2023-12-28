from odoo import models, fields


class PosConfig(models.Model):
    _inherit = "pos.config"

    scan_barcode_scale_by_price_with_tax = fields.Boolean(
        related="company_id.scan_barcode_scale_by_price_with_tax", readonly=False
    )
