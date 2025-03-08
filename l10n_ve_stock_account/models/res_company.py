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
