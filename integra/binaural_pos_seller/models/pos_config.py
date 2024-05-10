from odoo import fields, models


class PosConfig(models.Model):
    _inherit = "pos.config"

    use_seller_from_order = fields.Selection(
        related="company_id.use_seller_from_order",
        readonly=False,
    )
