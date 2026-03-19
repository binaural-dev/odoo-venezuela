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

    invoice_cron_time = fields.Float(required=True, default=18.0)

    indexed_dispatch_guide = fields.Boolean(
        string="Indexed Dispatch Guide",
        default=False,
        help="If enabled, dispatch guide amounts will use the date of the stock picking for currency conversion.",
    )
    
    hide_disc_field_dispatch_guide = fields.Boolean(
        string="Hide discount field in dispatch guide",
        default=False,
        help="If enabled, the discount field will be hidden in the dispatch guide.",
    )

    hide_weight_field_dispatch_guide = fields.Boolean(
        string="Hide weight field in dispatch guide",
        default=False,
        help="If enabled, the weight field will be hidden in the dispatch guide.",
    )

    donation_account_id = fields.Many2one(
        "account.account",
        check_company=True,
        string="Donation Account",
        readonly=False,
        domain=[
            ("account_type", "=", "expense"),
        ],
    )
