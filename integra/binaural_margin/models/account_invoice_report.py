from odoo import api, fields, models


class AccountInvoiceReport(models.Model):
    _inherit = "account.invoice.report"

    margin = fields.Float("Price Margin",digits="Product Price")

    margin_percent = fields.Float("Margin (%)", group_operator="avg")

    latest_standard_price_margin = fields.Float("Latest Cost Margin")
    latest_standard_price_margin_percent = fields.Float(
        "Latest Cost Margin (%)", group_operator="avg"
    )

    @api.model
    def _select(self):
        return (
            super()._select()
            + ", line.margin_percent as margin_percent, line.margin as margin, "
            "line.latest_standard_price_margin as latest_standard_price_margin, "
            "line.latest_standard_price_margin_percent as latest_standard_price_margin_percent"
        )
