from odoo import api, fields, models, _


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    use_invoice_rate_from_purchase_order = fields.Boolean(
        related="company_id.use_invoice_rate_from_purchase_order",
        help=(
            "Check this if you want the rate of the invoice to be taken from its purchase order."
            " Else it will take the rate of the date when it is created."
        ),
        readonly=False,
    )
    update_purchase_order_rate_using_date_order = fields.Boolean(
        related="company_id.update_purchase_order_rate_using_date_order",
        help=(
            "When checked, the rate of the purchase order will be updated using the date order"
            " whenever it changes. Else, when the rate is already set, it will not be updated."
        ),
        readonly=False,
    )
