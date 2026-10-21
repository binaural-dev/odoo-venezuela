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
    skip_vendor_bill_today_accounting_date = fields.Boolean(
        string="Skip Vendor Bill Accounting Date Adjustment",
        default=False,
        help="When activated, vendor bills dated before today keep Odoo's native "
        "accounting date (last day of the period) instead of using today's date.",
    )
    mandatory_contact_in_payable_or_receivable_accounting_accounts = fields.Boolean()