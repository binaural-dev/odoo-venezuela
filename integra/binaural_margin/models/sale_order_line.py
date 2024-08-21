from odoo import api, fields, models, _


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    latest_standard_price_margin = fields.Float(
        "Latest Cost Margin",
        compute="_compute_latest_standard_price_margin",
        store=True,
    )
    latest_standard_price_margin_percent = fields.Float(
        "Latest Cost Margin (%)",
        compute="_compute_latest_standard_price_margin",
        store=True,
    )

    @api.depends("product_uom_qty", "latest_standard_price")
    def _compute_latest_standard_price_margin(self):
        for line in self:
            line.latest_standard_price_margin = line.price_subtotal - (
                line.latest_standard_price * line.product_uom_qty
            )
            line.latest_standard_price_margin_percent = (
                line.price_subtotal and line.latest_standard_price_margin / line.price_subtotal
            )
