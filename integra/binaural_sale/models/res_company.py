from odoo import api, fields, models, _


class ResCompany(models.Model):
    _inherit = "res.company"

    use_invoice_rate_from_sale_order = fields.Boolean(
        help=(
            "Check this if you want the rate of the invoice to be taken from its sale order."
            " Else it will take the rate of the date when it is created."
        )
    )
    not_allow_sell_products = fields.Boolean(
        "Dont allow sell products without quantity", default=False
    )

