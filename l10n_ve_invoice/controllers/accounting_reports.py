from datetime import datetime
from odoo import http
from werkzeug.exceptions import BadRequest, NotFound

class AccountingReportsController(http.Controller):
    @staticmethod
    def _parse_int_param(kw, param_name, default_value, allow_zero=False):
        raw_value = kw.get(param_name, default_value)
        if raw_value in (None, ""):
            raw_value = default_value

        try:
            parsed_value = int(raw_value)
        except (TypeError, ValueError):
            raise BadRequest(f"Invalid parameter: {param_name}")

        if allow_zero:
            if parsed_value < 0:
                raise BadRequest(f"Invalid parameter: {param_name}")
        elif parsed_value <= 0:
            raise BadRequest(f"Invalid parameter: {param_name}")

        return parsed_value

    @staticmethod
    def _get_wizard_for_report(env_request, company_id, wizard_id, report_type):
        report_model = env_request["wizard.accounting.reports"]
        domain = [
            ("create_uid", "=", env_request.uid),
            ("report", "=", report_type),
            ("company_id", "=", company_id),
        ]
        if wizard_id:
            domain.append(("id", "=", wizard_id))

        wizard = report_model.search(domain, order="id desc", limit=1)
        if not wizard:
            raise NotFound()

        return wizard

    @http.route("/web/download_sales_book", type="http", auth="user")
    def download_sales_book(self, **kw):
        env_request = http.request.env
        company_id = self._parse_int_param(kw, "company_id", env_request.company.id)
        wizard_id = self._parse_int_param(kw, "wizard_id", 0, allow_zero=True)
        sale_book = self._get_wizard_for_report(env_request, company_id, wizard_id, "sale")

        file = sale_book.generate_sales_book(company_id)

        return http.request.make_response(
            file,
            headers=[
                (
                    "Content-Type",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                ),
                (
                    "Content-Disposition",
                    "attachment;filename=Libro_de_venta.xlsx"
                )
            ]
        )

    @http.route("/web/download_purchase_book", type="http", auth="user")
    def download_purchase_book(self, **kw):
        env_request = http.request.env
        company_id = self._parse_int_param(kw, "company_id", env_request.company.id)
        wizard_id = self._parse_int_param(kw, "wizard_id", 0, allow_zero=True)
        purchase_book = self._get_wizard_for_report(env_request, company_id, wizard_id, "purchase")

        file = purchase_book.generate_purchases_book(company_id)
        
        return http.request.make_response(
            file,
            headers=[
                (
                    "Content-Type",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                ),
                (
                    "Content-Disposition",
                    "attachment;filename=Libro_de_compra.xlsx"
                )
            ]
        )
