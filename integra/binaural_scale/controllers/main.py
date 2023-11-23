from odoo import http, _
from odoo.http import request, content_disposition


class ProductsPLU(http.Controller):
    @http.route("/web/binary/download_products_plu_csv", type="http", auth="user")
    def download_products_csv(self, company_id, **kwards):
        product_template = request.env["plu.product"].sudo().create({"company_id": int(company_id)})
        file = product_template.generate_plu_file()
        return request.make_response(
            file,
            headers=[
                (
                    "Content-Type",
                    "text/csv",
                ),
                ("Content-Disposition", "attachment;filename=Lista_de_productos.csv"),
            ],
        )

    @http.route("/web/binary/download_products_plu_cas_5200", type="http", auth="user")
    def download_plu_file_cas_5200(self, company_id, **kwards):
        product_template = request.env["plu.product"].sudo().create({"company_id": int(company_id)})
        file = product_template.generate_plu_file_cas5200()
        return request.make_response(
            file,
            headers=[
                ("Content-Type", "application/vnd.ms-excel"),
                ("Content-Disposition", content_disposition("demo.xls")),
            ],
        )
