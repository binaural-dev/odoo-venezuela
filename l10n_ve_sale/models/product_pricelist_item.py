from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ProductPricelistItem(models.Model):
    _inherit = "product.pricelist.item"

    price_without_tax = fields.Float(compute="_compute_prices_with_tax")
    price_with_tax = fields.Float(compute="_compute_prices_with_tax")

    # ====== COMPUTE METHODS =======#

    @api.depends("price")
    def _compute_prices_with_tax(self):
        for item in self:
            if not item.product_tmpl_id.taxes_id or not item.product_tmpl_id:
                item.price_without_tax = item.fixed_price
                item.price_with_tax = item.fixed_price
                continue
            taxes = item.product_tmpl_id.taxes_id.compute_all(
                item.fixed_price, item.currency_id, 1, product=item.product_tmpl_id
            )
            item.price_without_tax = taxes["total_excluded"]
            item.price_with_tax = taxes["total_included"]

    @api.constrains("fixed_price")
    def _check_fixed_price(self):
        for item in self:
            if item.fixed_price < 0:
                raise ValidationError(_("Price cannot be negative"))
