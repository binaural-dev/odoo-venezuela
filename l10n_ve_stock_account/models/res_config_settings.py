from odoo import _, api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    customer_journal_id = fields.Many2one(related="company_id.customer_journal_id", readonly=False)

    vendor_journal_id = fields.Many2one(related="company_id.vendor_journal_id", readonly=False)

    internal_consigned_journal_id = fields.Many2one(
        related="company_id.internal_consigned_journal_id", readonly=False
    )

    invoice_cron_type = fields.Selection(related="company_id.invoice_cron_type", readonly=False)
    invoice_cron_time = fields.Float(related="company_id.invoice_cron_time", readonly=False)

    hide_price_on_dispatch_guide = fields.Boolean(
        related="company_id.hide_price_on_dispatch_guide", readonly=False
    )
