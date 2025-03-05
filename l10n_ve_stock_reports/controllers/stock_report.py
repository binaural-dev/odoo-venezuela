from datetime import datetime
from odoo import http


class StockReportsController(http.Controller):
    @http.route("/web/download_stock_book", type="http", auth="user")
    def download_stock_book(self, **kw):
        stock_book_model = http.request.env["wizard.stock.book.report"]
        company_id = int(kw.get("company_id", 1))
        stock_book = stock_book_model.search([], order="id desc", limit=1)

        file = stock_book.generate_stocks_book(company_id)

        return http.request.make_response(
            file,
            headers=[
                (
                    "Content-Type",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                ),
                (
                    "Content-Disposition",
                    "attachment;filename=Libro_de_Inventario.xlsx"
                )
            ]
        )