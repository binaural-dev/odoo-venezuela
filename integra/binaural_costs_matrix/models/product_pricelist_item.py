from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class ProductPricelistItem(models.Model):
    _inherit = "product.pricelist.item"

    brand_id = fields.Many2one(related="product_tmpl_id.brand_id", store=True)

    purchase_price = fields.Float(
        string="Cost",
        related="product_tmpl_id.standard_price",
        digits="Product Price",
        store=True,
    )

    latest_standard_price = fields.Monetary(
        string="Latest Cost",
        related="product_tmpl_id.latest_standard_price",
        digits="Product Price",
        store=True,
    )

    margin = fields.Float(
        compute="_compute_margin",
        digits="Product Price",
        store=True,
    )
    margin_percent = fields.Float(
        "Margin (%)",
        compute="_compute_margin",
        store=True,
    )
    latest_standard_price_margin = fields.Float(
        compute="_compute_margin",
        digits="Product Price",
        store=True,
    )
    latest_standard_price_margin_percent = fields.Float(
        "Latest Standard Price Margin (%)",
        compute="_compute_margin",
        store=True,
    )
    categ_id = fields.Many2one(
        related="product_tmpl_id.categ_id",
        store=True,
    )

    @api.depends("fixed_price", "latest_standard_price", "purchase_price")
    def _compute_margin(self):
        for line in self:
            line.margin = line.fixed_price - line.purchase_price
            line.margin_percent = line.fixed_price and line.margin / line.fixed_price
            line.latest_standard_price_margin = line.fixed_price - line.latest_standard_price

            line.latest_standard_price_margin_percent = (
                line.fixed_price and line.latest_standard_price_margin / line.fixed_price
            )
