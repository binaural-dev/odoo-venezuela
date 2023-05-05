from odoo import api, fields, models, _


class ResCompany(models.Model):
    _inherit = "res.company"

    use_invoice_rate_from_purchase_order = fields.Boolean(
        help=(
            "Check this if you want the rate of the invoice to be taken from its purchase order."
            " Else it will take the rate of the date it is created."
        )
    )
