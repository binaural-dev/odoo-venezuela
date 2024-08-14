from odoo import api, fields, models

class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    list_price = fields.Float(
        compute="_compute_list_price",
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

    @api.depends("product_id")
    def _compute_list_price(self):
        for line in self:
            line.list_price = line.product_id.list_price

    @api.depends("price_subtotal", "product_qty", "latest_standard_price", "list_price")
    def _compute_margin(self):
        for line in self:
            line.margin = line.list_price - (line.price_unit * line.product_qty)
            line.margin_percent = line.list_price and line.margin / line.list_price
            line.latest_standard_price_margin = line.list_price - (
                line.latest_standard_price * line.product_qty
            )
            line.latest_standard_price_margin_percent = (
                line.list_price and line.latest_standard_price_margin / line.list_price
            )
