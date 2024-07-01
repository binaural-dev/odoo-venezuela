from odoo import models, _
from collections import defaultdict
from odoo.exceptions import UserError


class HrPayslipRunReport(models.AbstractModel):
    _name = "report.binaural_hr_payroll.report_pre_payslip_run"

    def _get_report_values(self, docids, data=None):
        if len(docids) != 1:
            raise UserError(_("The pre payslip run report should be called upon one record."))
        docs = self.env["hr.payslip.run"].browse(docids)
        vef_currency = self.env.ref("base.VEF")
        total_field = "total" if docs.company_id.currency_id == vef_currency else "foreign_total"
        totals_per_line = self._get_totals_per_line(docs, total_field)
        return {
            "doc_ids": docids,
            "doc_model": "hr.payslip.run",
            "docs": docs,
            "data": data,
            "get_totals_per_line": totals_per_line,
            "get_total_net": self._get_total_net(totals_per_line),
            "vef_currency": vef_currency,
        }

    def _get_totals_per_line(self, docs, total_field):
        totals_per_line = defaultdict(lambda: {"quantity": 0.0, "total": 0.0})
        categories_not_to_sum = ["DEV", "NET", "OC", "OCV", "DEVVAC", "GROSS"]
        for line in (
            docs.slip_ids.mapped("line_ids")
            .filtered(lambda l: l.category_id.code not in categories_not_to_sum)
            .sorted(total_field, True)
        ):
            totals_per_line[line.name]["quantity"] += line.quantity
            totals_per_line[line.name]["total"] += getattr(line, total_field)
        return totals_per_line

    def _get_total_net(self, totals_per_line):
        return sum(line["total"] for line in totals_per_line.values())
