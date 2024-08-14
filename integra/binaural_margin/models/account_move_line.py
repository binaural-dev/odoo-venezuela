from odoo import api, fields, models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    purchase_price = fields.Float(
        string="Cost",
        compute="_compute_purchase_price",
        digits="Product Price",
        store=True,
        readonly=False,
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
        "Latest Cost Margin",
        compute="_compute_margin",
        store=True,
    )
    latest_standard_price_margin_percent = fields.Float(
        "Latest Cost Margin (%)",
        compute="_compute_margin",
        store=True,
    )

    @api.depends("product_id")
    def _compute_purchase_price(self):
        for line in self:
            product_id = line.product_id
            line.purchase_price = product_id.standard_price

    @api.depends("purchase_price", "quantity", "latest_standard_price")
    def _compute_margin(self):
        for line in self:
            line.margin = line.price_subtotal - (line.purchase_price * line.quantity)
            line.margin_percent = line.price_subtotal and line.margin / line.price_subtotal
            line.latest_standard_price_margin = line.price_subtotal - (
                line.latest_standard_price * line.quantity
            )
            line.latest_standard_price_margin_percent = (
                line.price_subtotal and line.latest_standard_price_margin / line.price_subtotal
            )
