import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):
    _inherit = "res.company"

    customer_journal_id = fields.Many2one(
        "account.journal",
        string="Customer Journal",
        help="To add customer journal",
    )
    vendor_journal_id = fields.Many2one(
        "account.journal",
        string="Vendor Journal",
        help="To add vendor journal",
    )

    internal_consigned_journal_id = fields.Many2one(
        "account.journal",
        string="Internal Journal",
        help="To add internal journal",
    )

    invoice_cron_type = fields.Selection(
        [("last_business_day", _("Last Business Day")), ("last_day", _("Last Day"))],
        string="Date Cron Invoice",
        default="last_business_day",
        required=True,
    )

    optional_internal_movement_guidance = fields.Boolean(
        "Internal picking with dispatched guidance ptional",
        default=False
    )
    invoice_cron_time = fields.Float(required=True, default=18.0)
