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

    @http.route(
        "/validate_products_in_warehouse", type="json", auth="public", website=False, sitemap=False
    )
    def validate_products_in_warehouse(self, product_ids, picking_type_id, qty, **kwargs):
        data = {"status": 200, "msg": "Success", "msg_error": False}
        products_name = []

        if product_ids:
            product_ids = set(product_ids)
            products = request.env["product.product"].search([("id", "in", list(product_ids))])
            warehouse_id_pos = request.env["stock.picking.type"].browse(picking_type_id[0]).warehouse_id
            stock_quant = request.env["stock.quant"].search([
                ("product_tmpl_id", "in", products.product_tmpl_id.ids),
                ("on_hand", "=", True),
                ("product_tmpl_id.type", "!=", "service")
            ])

            product_qty_map = dict(zip(products.ids, qty))
            for quant in stock_quant:
                if product_qty_map.get(quant.product_tmpl_id.id, 0) > quant.available_quantity:
                    data["msg_error"] = _(
                        "The product '%s' does not have enough stock in the warehouse '%s'" % (
                            quant.product_tmpl_id.name,
                            quant.warehouse_id.name,
                        )
                    )
                    return data
                if quant.warehouse_id not in warehouse_id_pos:
                    products_name.append(quant.product_tmpl_id.name)

        if products_name:
            data["msg_error"] = _(
                "The products '%s' are not available in stock in the warehouse %s" % (
                    ", ".join(products_name),
                    warehouse_id_pos.name,
                )
            )

        return data
