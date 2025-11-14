from datetime import datetime
from odoo import http ,SUPERUSER_ID
from odoo.api import Environment # <--- IMPORTANTE: Necesitas esta importación
from odoo.exceptions import UserError

class AccountingReportsController(http.Controller):
    @http.route("/web/download_sales_book", type="http", auth="user")
    def download_sales_book(self, **kw):
        
        env_request = http.request.env
        
        env_su = Environment(env_request.cr, SUPERUSER_ID, env_request.context)
        
        sale_book_model_su = env_su["wizard.accounting.reports"]
        
        company_id = int(kw.get("company_id", 1))
        
        sale_book = sale_book_model_su.search([], order="id desc", limit=1)
        
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
        
        env_su = Environment(env_request.cr, SUPERUSER_ID, env_request.context)
        
        purchase_book_model_su = env_su["wizard.accounting.reports"]
        
        company_id = int(kw.get("company_id", 1))
        
        purchase_book = purchase_book_model_su.search([], order="id desc", limit=1)
        
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