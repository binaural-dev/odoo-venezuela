import logging
import json

from odoo import http, _
from odoo.http import request
from odoo.osv import expression

_logger = logging.getLogger(__name__)

class ValidateQtyProducts(http.Controller):
    @http.route(
        "/validate_products_order", type="json", auth="public", website=False, sitemap=False
    )
    def validate_products_order(self, lines, qty, **kwargs):
        if lines and qty:
            product_qty_position = 0
            for product in lines:
                product_id = (
                    request.env["product.product"].search([("id", "=", product)]).product_tmpl_id
                )
                data = {"status": 200, "msg": "Success"}
                if (
                    product_id.detailed_type == "product"
                    and product_id.qty_available < qty[product_qty_position]
                ):
                    data.update(
                        {
                            "msg_error": product_id.name,
                        }
                    )
                    return data
                product_qty_position += 1

            return data
    
    @http.route("/validate_products_in_warehouse", type="json", auth="public", website=False, sitemap=False)
    def validate_products_in_warehouse(
        self, product_ids, picking_type_id, **kwargs
    ):  
        data = {"status": 200, "msg": "Success", "msg_error": False}
        products_name = ''
        if product_ids:
            for product in product_ids:
                product_id = request.env['product.product'].search([('id', '=', product)]).product_tmpl_id
                warehouse_id_pos = request.env["stock.picking.type"].search([('id', '=', picking_type_id[0])]).warehouse_id

                if product_id:
                    stock_quant = request.env["stock.quant"].search(
                        [
                            ("product_tmpl_id", "=", product_id.id),
                            ("on_hand", "=", True),
                            ("product_tmpl_id.type", "!=", "service"),
                        ]
                    )
                    warehouse_ids = request.env["stock.warehouse"]

                    for quant in stock_quant:
                        warehouse_ids += quant.warehouse_id

                    if warehouse_id_pos not in warehouse_ids:
                        products_name += f"{product_id.name} ,"
        if products_name:
            data.update(
                {
                    "msg_error": _(
                        "The product's '%s' is not found in warehouse %s",
                        products_name,
                        warehouse_id_pos.name,
                    ),
                }
            )

        return data