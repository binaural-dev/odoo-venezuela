from odoo import http, _
from odoo.http import request, Response


class ControllerMunicipalRetentionXlsx(http.Controller):
    @http.route("/web/get_excel_municipal_retentions_report", type="http", auth="user")
    def download_document(self, id):
        if not id:
            return request.not_found()

        report_obj = request.env["municipal.retention.xlsx.report"].browse(int(id))

        tabla = report_obj._get_excel_municipal_retention_report()

        name_document = _("Municipal Retention Report from {date_from} to {date_to}").format(
            date_from=report_obj.date_start.strftime("%d-%m-%Y"),
            date_to=report_obj.date_end.strftime("%d-%m-%Y"),
        )

        filecontent = report_obj._excel_file(tabla, name_document)

        if not filecontent:
            return Response(
                _("There is no data to show."), content_type="text/html;charset=utf-8", status=500
            )
        return request.make_response(
            filecontent,
            [
                (
                    "Content-Type",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                ),
                ("Content-Length", len(filecontent)),
                ("Content-Disposition", f"attachment; filename={name_document}.xlsx"),
            ],
        )
