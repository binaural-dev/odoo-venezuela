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
    vendor_bill_accounting_date_on_registration = fields.Boolean(
        string="Keep Registration Date as Vendor Bill Accounting Date",
        default=True,
        help="When enabled, the accounting date of vendor bills is set to the registration "
        "date. It is not automatically filled with the last day of the journal period and "
        "it does not change when the invoice date or the journal changes. The user can "
        "still edit it manually.",
    )
    sync_vendor_bill_accounting_date_with_invoice_date = fields.Boolean(
        string="Sync Vendor Bill Accounting Date with Invoice Date",
        default=False,
        help="When enabled (requires keeping the registration date), changing the invoice "
        "date in the form sets the accounting date to the same date. It does not act through "
        "ORM writes, it does not act if the date violates a lock date, and changing the "
        "journal never modifies the accounting date.",
    )
    mandatory_contact_in_payable_or_receivable_accounting_accounts = fields.Boolean()