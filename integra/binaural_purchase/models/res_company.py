from odoo import api, fields, models, _


class ResCompany(models.Model):
    _inherit = "res.company"

    use_invoice_rate_from_purchase_order = fields.Boolean(
        help=(
            "Check this if you want the rate of the invoice to be taken from its purchase order."
            " Else it will take the rate of the date it is created."
        )
    )
    update_purchase_order_rate_using_date_order = fields.Boolean(
        help=(
            "When checked, the rate of the purchase order will be updated using the date order"
            " whenever it changes. Else, when the rate is already set, it will not be updated."
        )
    )

