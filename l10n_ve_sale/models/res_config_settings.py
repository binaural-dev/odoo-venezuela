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

    convert_currency_from_sale_order = fields.Boolean(
        related='company_id.convert_currency_from_sale_order',
        readonly=False,
    )

    global_discount_account_id = fields.Many2one(
        related="company_id.global_discount_account_id", readonly=False
    )

    discount_method_limit_enabled = fields.Boolean(related="company_id.discount_method_limit_enabled", readonly=False)

    discount_allow_line_percent = fields.Boolean(related="company_id.discount_allow_line_percent", readonly=False)

    discount_allow_line_amount = fields.Boolean(related="company_id.discount_allow_line_amount", readonly=False)

    discount_allow_global_subtotal = fields.Boolean(related="company_id.discount_allow_global_subtotal", readonly=False)

    discount_allow_global_total = fields.Boolean(related="company_id.discount_allow_global_total", readonly=False)

    discount_max_limit_enabled = fields.Boolean(related="company_id.discount_max_limit_enabled", readonly=False)

    discount_max_line = fields.Float(related="company_id.discount_max_line", readonly=False)

    discount_max_global_subtotal = fields.Float(related="company_id.discount_max_global_subtotal", readonly=False)

    discount_max_global_total = fields.Float(related="company_id.discount_max_global_total", readonly=False)

    discount_approval_enabled = fields.Boolean(related="company_id.discount_approval_enabled", readonly=False)
