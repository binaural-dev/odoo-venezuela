from odoo import _, api, fields, models

from .res_company import INTERNAL_TRANSFER_REASON_CODES


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    customer_journal_id = fields.Many2one(
        related="company_id.customer_journal_id", readonly=False
    )

    vendor_journal_id = fields.Many2one(
        related="company_id.vendor_journal_id", readonly=False
    )

    internal_consigned_journal_id = fields.Many2one(
        related="company_id.internal_consigned_journal_id", readonly=False
    )

    invoice_cron_type = fields.Selection(
        related="company_id.invoice_cron_type", readonly=False
    )
    invoice_cron_time = fields.Float(
        related="company_id.invoice_cron_time", readonly=False
    )

    indexed_dispatch_guide = fields.Boolean(
        related="company_id.indexed_dispatch_guide", readonly=False
    )
    hide_weight_field_dispatch_guide = fields.Boolean(
        related="company_id.hide_weight_field_dispatch_guide", readonly=False
    )

    internal_transfer_reason_id = fields.Many2one(
        related="company_id.internal_transfer_reason_id",
        readonly=False,
        string="Default Internal Transfer Reason",
        domain=[("code", "in", INTERNAL_TRANSFER_REASON_CODES)],
    )

    group_dispatch_note_print = fields.Boolean(
        related="company_id.group_dispatch_note_print",
        readonly=False,
        implied_group="l10n_ve_stock_account.group_dispatch_note_print",
    )
