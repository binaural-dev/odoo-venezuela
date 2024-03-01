from datetime import datetime
from odoo import http, _


class BinauralHrPayslipReports(http.Controller):
    @http.route("/web/binary/download_bnc_txt", type="http", auth="user")
    def download_bnc_txt(self, payment_method_id):
        bnc_txt = http.request.env["hr.payslip.payment.methods"].search(
            [("id", "=", payment_method_id)]
        )
        txt = bnc_txt.generate_bnc_txt()

        return http.request.make_response(
            txt["file"],
            headers=[
                ("Content-Type", "text/plain"),
                ("Content-Disposition", f"attachment; filename={txt['filename']}"),
            ],
        )
