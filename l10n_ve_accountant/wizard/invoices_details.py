from odoo import fields, models
from datetime import datetime
from dateutil.relativedelta import relativedelta


class InvoiceDetailsWizard(models.TransientModel):
    _name = "account.invoices.details"
    _description = "Invoices Details"
    _check_company_auto = True

    company_id = fields.Many2one("res.company", default=lambda self: self.env.company.id)
    date_from = fields.Date(required=True, default=datetime.today().replace(day=1))
    date_to = fields.Date(
        required=True, default=datetime.today().replace(day=1) + relativedelta(months=1, days=-1)
    )
    show_documents = fields.Boolean(default=True)

    def action_print(self):
        return self.env.ref("l10n_ve_accountant.report_account_invoices_details").report_action(
            self
        )
