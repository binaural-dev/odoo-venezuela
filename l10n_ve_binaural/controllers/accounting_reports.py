from datetime import datetime
from odoo import http


class AccountingReportsController(http.Controller):
    @http.route("/web/download_sales_book", type="http", auth="user")
    def download_sales_book(self, **kw):
        sale_book_model = http.request.env["wizard.accounting.reports"]
        company_id = int(kw.get("company_id", 1))
        sale_book = sale_book_model.search([], order="id desc", limit=1)

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
        purchase_book_model = http.request.env["wizard.accounting.reports"]
        company_id = int(kw.get("company_id", 1))
        purchase_book = purchase_book_model.search([], order="id desc", limit=1)

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
