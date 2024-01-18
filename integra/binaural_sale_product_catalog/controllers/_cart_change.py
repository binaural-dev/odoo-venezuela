from odoo import http
import json


class QtyChange(http.Controller):
    @http.route(["/qtyupdatecart"], type="http", auth="public", website=True)
    def QtyUpdate(self, **post):
        _sol_obj = http.request.env["sale.order"]
        _sol_obj.user_input_qty_sol(
            int(post.get("quantity")),
            int(post.get("product")),
            int(post.get("sale_id")),
            (post.get("name")),
            int(post.get("customer_lead")),
            float(post.get("list_price")),
        )
        return json.dumps({"message": True})
