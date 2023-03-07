from odoo import http
from odoo.http import request, serialize_exception, content_disposition

import logging


_logger = logging.getLogger(__name__)


class AccountingReportsController(http.Controller):
    @http.route("/web/get_excel", type="http", auth="user")
    def download_document(self, report, wizard, date_start, date_end, current_company_id):
        current_company = request.env["res.company"].browse(int(current_company_id))
        wizard_id = int(wizard)
        wizard = request.env["wizard.accounting.reports"].browse(wizard_id)
        
        filecontent = ""
        table = ""
        name = "%ss Book" % (report.capitalize())
        
        is_purchase = report == "purchase"

        if is_purchase:
            table = wizard._table_purchase_book(wizard_id, current_company)
            table_resume = wizard._table_resume_shopping_book(wizard_id, current_company)

        else:
            table = wizard._table_sale_book(wizard_id, current_company)
            table_resume = wizard._table_resume_sale_book(wizard_id, current_company)

        if not table.empty and name:
            if is_purchase:
                filecontent = wizard._excel_file_purchase(
                    table, name, date_start, date_end, table_resume, current_company
                )

            else:
                filecontent = wizard._excel_file_sale(
                    table, name, date_start, date_end, table_resume, current_company
                )

        filecontent_length = len(filecontent)
        file_content_disposition = content_disposition(f"{name}.xlsx")

        return request.make_response(
            filecontent,
            [
                ("Content-Type", "application/.xlsx"),
                ("Content-Length", filecontent_length),
                ("Content-Disposition", file_content_disposition),
            ],
        )
