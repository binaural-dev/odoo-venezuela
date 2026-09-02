from odoo import _, api, fields, models


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

    block_order_invoice_total_amount_overdue = fields.Float(
        string="Total amount overdue"
    )

    are_sale_lines_limited = fields.Boolean(
        "Limit the number of lines in the budget/sales order", default=False
    )
    
    maximum_sales_line_limit = fields.Integer()
    convert_currency_from_sale_order = fields.Boolean(
        string="Convert Currency From Sale Order",
        help=(
            "Check this if you want to convert the price unit of the customer "
            "invoice lines based on the sale order, using the invoice rate. "
            "It cannot be combined with pricelist rules for the same products: "
            "if the invoice pricelist defines a rule for a product, the "
            "recalculation raises an error instead of overriding it."
        ),
        default=False,
    )
