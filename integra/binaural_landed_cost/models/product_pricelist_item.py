from odoo import fields, models


class ProductPricelistItem(models.Model):
    _inherit = "product.pricelist.item"

    base = fields.Selection(
        selection_add=[("latest_standard_price", "Latest Standard Price")],
        ondelete={"latest_standard_price": "set default"},
    )
