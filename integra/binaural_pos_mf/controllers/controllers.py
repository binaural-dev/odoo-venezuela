from datetime import datetime

from odoo import http, _


class BinauralNominaReportes(http.Controller):
    @http.route("/web/binary/download_sales_book", type="http", auth="user")
    def download_sales_book(self, date_from, date_to):
        sales_book = http.request.env["wizard.sales.book"].search([])
        file = sales_book.generate_sales_book(
            datetime.strptime(date_from, "%Y-%m-%d"), datetime.strptime(date_to, "%Y-%m-%d")
        )
        return http.request.make_response(
            file,
            headers=[
                (
                    "Content-Type",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                ),
                ("Content-Disposition", "attachment;filename=Libro_de_venta.xlsx"),
            ],
        )
