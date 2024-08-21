from odoo import api, fields, models, _


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    latest_standard_price = fields.Monetary(
        compute="_compute_latest_standard_price", precompute=True, store=True
    )

    @api.depends("product_id")
    def _compute_latest_standard_price(self):
        for line in self:
            line.latest_standard_price = line.product_id.latest_standard_price
