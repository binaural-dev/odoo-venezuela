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

    optional_internal_movement_guidance = fields.Boolean(
        "Internal picking with dispatched guidance ptional",
        related='company_id.optional_internal_movement_guidance',
        readonly=False,
    )