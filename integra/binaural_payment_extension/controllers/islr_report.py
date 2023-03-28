from odoo import http
import pandas as pd


class IslrReportController(http.Controller):
    @http.route("/web/download_islr_report", type="http", auth="user")
    def download_islr_report(self, report, wizard, start, end, current_company_id):
        islr_report_model = http.request.env["wizard.retention.islr"]
        company = http.request.env["res.company"].browse(int(current_company_id))
        islr_report = islr_report_model.search([], order="id desc", limit=1)

        table = islr_report._retention_islr_excel(company)
        file = islr_report._excel_file_retention_islr(
            table, "XML Retencion de ISLR", start, end, company
        )

        return http.request.make_response(
            file,
            headers=[
                (
                    "Content-Type",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                ),
                ("Content-Length", len(file)),
                ("Content-Disposition", "attachment; filename=ISLR_Report.xlsm;"),
            ],
        )
