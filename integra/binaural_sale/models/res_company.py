from odoo import api, fields, models, _


class ResCompany(models.Model):
    _inherit = "res.company"

    use_invoice_rate_from_sale_order = fields.Boolean(
        help=(
            "Check this if you want the rate of the invoice to be taken from its sale order."
            " Else it will take the rate of the date when it is created."
        )
    )
    update_sale_order_rate_using_date_order = fields.Boolean(
        help=(
            "When checked, the rate of the sale order will be updated using the date order whenever"
            " it changes. Else, when the rate is already set, it will not be updated."
        )
    )
    not_allow_sell_products = fields.Boolean(
        "Dont allow sell products without quantity", default=False
    )

    block_order_invoice_payment_state = fields.Selection(
        string="Payment State",
        selection=[
            ('not_paid', 'Not paid'),
            ('in_payment', 'In payment process')
        ]
    )

    block_order_invoice_total_amount = fields.Float(
        string="Total amount"
    )
    