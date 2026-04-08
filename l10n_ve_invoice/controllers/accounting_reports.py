from datetime import datetime
from odoo import http

class AccountingReportsController(http.Controller):
    @http.route("/web/download_sales_book", type="http", auth="user")
    def download_sales_book(self, **kw):
        env_request = http.request.env
        sale_book_model = env_request["wizard.accounting.reports"]

        company_id = int(kw.get("company_id", 1))
        wizard_id = int(kw.get("wizard_id", 0) or 0)
        domain = [
            ("create_uid", "=", env_request.uid),
            ("report", "=", "sale"),
            ("company_id", "=", company_id),
        ]
        if wizard_id:
            domain.append(("id", "=", wizard_id))
        sale_book = sale_book_model.search(domain, order="id desc", limit=1)

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
        purchase_book_model = env_request["wizard.accounting.reports"]

        company_id = int(kw.get("company_id", 1))
        wizard_id = int(kw.get("wizard_id", 0) or 0)
        domain = [
            ("create_uid", "=", env_request.uid),
            ("report", "=", "purchase"),
            ("company_id", "=", company_id),
        ]
        if wizard_id:
            domain.append(("id", "=", wizard_id))
        purchase_book = purchase_book_model.search(domain, order="id desc", limit=1)

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
