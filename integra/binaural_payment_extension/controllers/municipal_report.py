from odoo import http, _
from odoo.http import request, Response


class ControllerMunicipalRetentionXlsx(http.Controller):
    @http.route("/web/get_xlsx_municipal_retentions_report", type="http", auth="user")
    def download_xlsx_report(self, report_id):
        if not id:
            return request.not_found()

        report_obj = request.env["municipal.retention.xlsx.report"].browse(int(report_id))

        table = report_obj._get_xlsx_municipal_retention_report()

        name_document = _("Municipal Retention Report from {date_from} to {date_to}").format(
            date_from=report_obj.date_start.strftime("%d-%m-%Y"),
            date_to=report_obj.date_end.strftime("%d-%m-%Y"),
        )

        filecontent = report_obj._xlsx_file(table, name_document)

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

    @http.route("/web/get_xlsx_municipal_retention", type="http", auth="user")
    def download_xlsx_document(self, retention_id):
        filecontent = ""
        report_obj = request.env["municipal.retention.xlsx"]

        if not retention_id:
            return request.not_found()

        tabla = report_obj.get_xlsx_municipal_retention(int(retention_id))
        retention = request.env["account.retention"].browse(int(retention_id))
        name_document = ""

        if retention.state == "draft":
            name_document = _("Draft Municipal Ret %s", retention.date.strftime("%d-%m-%Y"))
        elif retention.state == "emitted":
            name_document = _("Municipal Ret {retention_name} {retention_date}").format(
                retention_name=retention.name, retention_date=retention.date.strftime("%d-%m-%Y")
            )
        else:
            name_document = _("Cancelled Municipal Ret")

        filecontent = report_obj.xlsx_file(tabla, name_document, int(retention_id))

        if not filecontent:
            return Response(
                "There is no data to show", content_type="text/html;charset=utf-8", status=500
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


class ControllerMunicipalRetentionPatentXlsx(http.Controller):
    @http.route("/web/get_xlsx_municipal_retention_report_patent", type="http", auth="user")
    def download_document(self, report_id):
        filecontent = ""
        if not id:
            return request.not_found()

        report_obj = request.env["municipal.retention.patent.report"].browse(int(report_id))

        table = report_obj._get_xlsx_municipality_retention_report()

        name_document = _("Municipal Patent Report from {date_start} to {date_end}").format(
            date_start=report_obj.date_start.strftime("%d-%m-%Y"),
            date_end=report_obj.date_end.strftime("%d-%m-%Y"),
        )

        filecontent = report_obj._xlsx_file(table, name_document)

        if not filecontent or len(filecontent) == 0:
            return Response(
                _("There is no data to show"), content_type="text/html;charset=utf-8", status=500
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
