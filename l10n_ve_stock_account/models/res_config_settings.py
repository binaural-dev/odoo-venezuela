from odoo import _, api, fields, models


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

    donation_account_id = fields.Many2one(
        "account.account", "Donation Account", related="company_id.donation_account_id", readonly=False
    )
    hide_disc_field_dispatch_guide = fields.Boolean(
        related="company_id.hide_disc_field_dispatch_guide", readonly=False
    )

    hide_weight_field_dispatch_guide = fields.Boolean(
        related="company_id.hide_weight_field_dispatch_guide", readonly=False
    )

