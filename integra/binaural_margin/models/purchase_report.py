from odoo import api, fields, models, _


class PurchaseReport(models.Model):
    _inherit = "purchase.report"

    margin = fields.Float(
        digits="Product Price",
        store=True,
        group_operator="avg",
    )

    margin_percent = fields.Float("Margin (%)", store=True, group_operator="avg")

    latest_standard_price_margin = fields.Float(store=True, group_operator="avg")
    latest_standard_price_margin_percent = fields.Float(
        "Latest Standard Price Margin (%)", store=True, group_operator="avg"
    )

    @api.model
    def _select(self):
        return (
            super()._select() + ", l.margin_percent as margin_percent, l.margin as margin, "
            "l.latest_standard_price_margin as latest_standard_price_margin, "
            "l.latest_standard_price_margin_percent as latest_standard_price_margin_percent"
        )

    def _group_by(self):
        return (
            super()._group_by() + ", l.margin_percent, l.margin, l.latest_standard_price_margin, "
            "l.latest_standard_price_margin_percent"
        )
