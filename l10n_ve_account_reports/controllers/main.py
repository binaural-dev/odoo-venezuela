import json

from werkzeug.exceptions import InternalServerError

from odoo import http
from odoo.addons.account_reports.controllers.main import AccountReportController
from odoo.http import request
from odoo.models import check_method_name
from odoo.tools.misc import html_escape


class AccountReportForeignCurrencyController(AccountReportController):
    @http.route("/account_reports", type="http", auth="user", methods=["POST"], csrf=False)
    def get_report(self, options, file_generator, usd_report=False, **kwargs):
        """
        Ensure the report that is gonna be exported is in the currency that it should be.
        """
        uid = request.uid
        options = json.loads(options)
        allowed_company_ids = [
            company_data["id"] for company_data in options.get("multi_company", [])
        ]
        if not allowed_company_ids:
            company_str = request.httprequest.cookies.get(
                "cids", str(request.env.user.company_id.id)
            )
            allowed_company_ids = [int(str_id) for str_id in company_str.split(",")]

        report = (
            request.env["account.report"]
            .with_user(uid)
            .with_context(
                allowed_company_ids=allowed_company_ids,
                usd_report=True if usd_report == "true" else False,
            )
            .browse(options["report_id"])
        )

        try:
            check_method_name(file_generator)
            generated_file_data = report.dispatch_report_action(options, file_generator)
            file_content = generated_file_data["file_content"]
            file_type = generated_file_data["file_type"]
            response_headers = self._get_response_headers(
                file_type, generated_file_data["file_name"], file_content
            )

            if file_type == "xlsx":
                response = request.make_response(None, headers=response_headers)
                response.stream.write(file_content)
            else:
                response = request.make_response(file_content, headers=response_headers)

            if file_type == "zip":
                # Adding direct_passthrough to the response and giving it a file
                # as content means that we will stream the content of the file to the user
                # Which will prevent having the whole file in memory
                response.direct_passthrough = True

            return response
        except Exception as e:
            se = http.serialize_exception(e)
            error = {"code": 200, "message": "Odoo Server Error", "data": se}
            res = request.make_response(html_escape(json.dumps(error)))
            raise InternalServerError(response=res) from e
