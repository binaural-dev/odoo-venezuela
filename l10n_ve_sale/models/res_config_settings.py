from odoo import _, api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    use_invoice_rate_from_sale_order = fields.Boolean(
        related="company_id.use_invoice_rate_from_sale_order",
        help=(
            "Check this if you want the rate of the invoice to be taken from its sale order."
            " Else it will take the rate of the date when it is created."
        ),
        readonly=False,
    )
    update_sale_order_rate_using_date_order = fields.Boolean(
        related="company_id.update_sale_order_rate_using_date_order",
        help=(
            "When checked, the rate of the sale order will be updated using the date order whenever"
            " it changes. Else, when the rate is already set, it will not be updated."
        ),
        readonly=False,
    )
    not_allow_sell_products = fields.Boolean(related='company_id.not_allow_sell_products', readonly=False)

    block_order_invoice_payment_state = fields.Selection(
        related='company_id.block_order_invoice_payment_state',
        readonly=False
    )

    block_order_invoice_total_amount_overdue = fields.Float(
        related='company_id.block_order_invoice_total_amount_overdue',
        readonly=False
    )

    are_sale_lines_limited = fields.Boolean(
        related='company_id.are_sale_lines_limited',
        readonly=False
    )

    maximum_sales_line_limit = fields.Integer(
        related='company_id.maximum_sales_line_limit',
        readonly=False
    )
