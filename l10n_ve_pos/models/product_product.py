from odoo import _, api, models, fields

class ProductProduct(models.Model):
    _inherit = "product.product"

    pos_sale_on_order = fields.Boolean(
        string="Sale on Order in POS",
        related='product_tmpl_id.pos_sale_on_order',
        store=False,
    )