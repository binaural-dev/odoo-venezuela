import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):
    _inherit = "res.company"

    max_product_invoice = fields.Integer(default=23)
    group_sales_invoicing_series = fields.Boolean()
    show_total_on_usd_invoice = fields.Boolean(default=True)
    show_tag_on_usd_invoice = fields.Boolean(default=True)
    show_column_default_code_free_form = fields.Boolean(default=True)
    auto_select_debit_note_journal = fields.Boolean(default=False)
    block_invoice_display_date_upper_than_date = fields.Boolean()
    discount_type = fields.Selection(
        [("percent", "Percentage"), ("amount", "Fixed Amount")],
        string="Invoice Line Discount Type",
        default="percent",
        required=True,
        help="Discount field shown on invoice lines, applied to all "
        "invoices and lines of this company: native percentage, or a fixed "
        "amount discount_fixed converted to its % equivalent.",
    )
