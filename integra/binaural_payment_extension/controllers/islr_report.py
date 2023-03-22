from odoo.addons.web.controllers.main import content_disposition
from odoo import http


class IslrReportController(http.Controller):
    @http.route("/web/download_islr_report", type="http", auth="user")
    def download_islr_report(self, **kw):
        islr_report_model = http.request.env["wizard.retention.islr"]
        islr_report = islr_report_model.search([], order="id desc", limit=1)

        file = islr_report.print_report()

        return http.request.make_response(
            file,
            headers=[
                (
                    "Content-Type",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                ),
                ("Content-Disposition", content_disposition("ISLR_Report.xlsm")),
            ],
        )
