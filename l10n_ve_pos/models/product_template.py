from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

class ProductTemplate(models.Model):
    _inherit = "product.template"

    pos_sale_on_order = fields.Boolean(
            string="Sale on Order in POS",
            help="Allow selling this product in POS even if it is not available in stock.",
            default=False,
            tracking=True,
        )