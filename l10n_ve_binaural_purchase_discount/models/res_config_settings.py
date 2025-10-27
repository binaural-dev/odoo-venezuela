from odoo import fields, models

class Company(models.TransientModel):
    _inherit = "res.config.settings"

    purchase_discount_product_id = fields.Many2one(
        related="company_id.purchase_discount_product_id",
        domain=[
            ('type', '=', 'service'),
            ('purchase_method', '=', 'purchase')
        ],
        readonly=False
    )