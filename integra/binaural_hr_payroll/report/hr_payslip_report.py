from odoo import models, api


class HrPayrollReportPayslipLang(models.AbstractModel):
    _name = "report.hr_payroll.report_payslip_lang"

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env["hr.payslip"].browse(docids)
        return {
            "docids": docids,
            "doc_model": "hr.payslip",
            "vef_currency": self.env.ref("base.VEF"),
            "docs": docs,
        }
