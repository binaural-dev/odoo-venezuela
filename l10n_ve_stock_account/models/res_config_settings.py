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
    hide_disc_field_dispatch_guide = fields.Boolean(
        related="company_id.hide_disc_field_dispatch_guide", readonly=False
    )

    hide_weight_field_dispatch_guide = fields.Boolean(
        related="company_id.hide_weight_field_dispatch_guide", readonly=False
    )

    seniat_email = fields.Char(related="company_id.seniat_email", readonly=False)

    def action_send_seniat_summary_now(self):
        self.ensure_one()
        sent = self.env["stock.picking"]._send_seniat_summary(self.company_id)
        if sent:
            message = _("The SENIAT summary email has been sent.")
            notification_type = "success"
        else:
            message = _("There are no unbilled dispatch guides to report.")
            notification_type = "warning"
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("SENIAT Summary"),
                "message": message,
                "type": notification_type,
                "sticky": False,
            },
        }

