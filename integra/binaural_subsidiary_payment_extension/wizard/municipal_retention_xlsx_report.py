from odoo import fields, models, _
from odoo.exceptions import ValidationError


class MunicipalRetentionXlsxReport(models.TransientModel):
    _inherit = "municipal.retention.xlsx.report"

    account_analytic_id = fields.Many2one(
        "account.analytic.account", string="Subsidiary", domain=[("is_subsidiary", "=", True)]
    )

    def print_xlsx(self):
        if not self.env.company.use_subsidiary_with_multiple_municipalities:
            return super().print_xlsx()

        self.env.context = self.with_context(
            do_not_validate_missing_tax_authorities_name_per_company=True
        ).env.context
        if self.account_analytic_id and not self.account_analytic_id.tax_authorities_name:
            raise ValidationError(_("The subsidiary has no tax authorities name"))

        return super().print_xlsx()

    def _get_tax_authorities_record(self, company):
        if not self.env.company.use_subsidiary_with_multiple_municipalities:
            return super()._get_tax_authorities_record(company)
        return self.account_analytic_id

    def _get_filtered_retention_lines(self, lines):
        if self.account_analytic_id:
            return lines.filtered(lambda l: l.account_analytic_id == self.account_analytic_id)
        return lines
