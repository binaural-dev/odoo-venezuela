from odoo import fields, models, _


class MunicipalRetentionPatentReport(models.TransientModel):
    _inherit = "municipal.retention.patent.report"

    account_analytic_id = fields.Many2one(
        "account.analytic.account",
        string="subsidiary",
        domain=[("is_subsidiary", "=", True)],
        required=True,
    )

    def _get_xlsx_file_domain(self):
        domain = super()._get_xlsx_file_domain()
        if self.account_analytic_id:
            domain.append(("move_id.account_analytic_id", "=", self.account_analytic_id.id))
        return domain

    def _get_xlsx_municipality_retention_report_domain(self):
        domain = super()._get_xlsx_municipality_retention_report_domain()
        if self.account_analytic_id:
            domain.append(("move_id.account_analytic_id", "=", self.account_analytic_id.id))
        return domain
