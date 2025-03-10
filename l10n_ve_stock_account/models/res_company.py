import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):
    _inherit = "res.company"

    # customer_journal_id = fields.Many2one(
    #     "account.journal",
    #     string="Customer Journal",
    #     help="To add customer journal",
    # )
    # vendor_journal_id = fields.Many2one(
    #     "account.journal",
    #     string="Vendor Journal",
    #     help="To add vendor journal",
    # )

    date_type_of_month = fields.Selection(
        selection=[
            ("business_day", "Business day of the month"), 
            ("of_month", "Of the month")
        ],
        default="business_day",
    )
