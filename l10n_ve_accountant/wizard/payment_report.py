from odoo import api, fields, exceptions, http, models, _
from odoo.exceptions import UserError, RedirectWarning, ValidationError


class PaymentReport(models.TransientModel):
    _name = "payment.report"

    payment_type = fields.Selection(
        [("outbound", "Outbound"), ("inbound", "Inbound")],
        string="Payment Type",
        default="outbound",
    )
    journal_id = fields.Many2one(
        "account.journal", required=True, domain=[("type", "in", ("bank", "cash"))]
    )
    start_date = fields.Date(string="Start Date", default=fields.Date.context_today, required=True)
    end_date = fields.Date(string="End Date", default=fields.Date.context_today, required=True)

    def generate_report_payment(self):
        data = {
            "form": {
                "payment_type": self.payment_type,
                "journal_id": self.journal_id.id,
                "start_date": self.start_date,
                "end_date": self.end_date,
            }
        }
        return self.env.ref("l10n_ve_accountant.action_report_all_payments").report_action(
            self, data=data
        )
