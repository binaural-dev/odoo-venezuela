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
    def validate_products_in_warehouse(self, product_ids, picking_type_id, qty,sell_kit_from_another_store, **kwargs):
        data = {"status": 200, "msg": "Success", "msg_error": False}
        products_name = ""
        if product_ids:
            product_qty_position = 0
            for product in product_ids:
                product_id = request.env["product.product"].browse(product).product_tmpl_id
                warehouse_id_pos = (
                    request.env["stock.picking.type"].browse(picking_type_id[0]).warehouse_id
                )
                current_product = product_qty_position
                product_qty_position += 1
                if product_id and product_id.detailed_type in ['product',]:
                    stock_quant = request.env["stock.quant"].search(
                        [
                            ("product_tmpl_id", "=", product_id.id),
                            ("on_hand", "=", True),
                            ("product_tmpl_id.type", "!=", "service"),
                        ]
                    )
                    if stock_quant:
                        product_in_warehouse_pos = False
                        quantity_available = 0.0
                        for quant in stock_quant:
                            if warehouse_id_pos == quant.warehouse_id:
                                product_in_warehouse_pos = True
                                quantity_available += (
                                    quant.available_quantity if quant.available_quantity > 0 else 0
                                )

                        if qty[current_product] > quantity_available and product_in_warehouse_pos:
                            data.update(
                                {
                                    "msg_error": _(
                                        "The product's '%s' You do not have enough stock in the warehouse %s",
                                        product_id.name,
                                        warehouse_id_pos.name,
                                    ),
                                }
                            )
                            return data
                        if not product_in_warehouse_pos and quantity_available == 0:
                            products_name += f"{product_id.name} ,"
                        continue
                    else:
                        data.update(
                            {
                                "msg_error": _(
                                    "The product's '%s' You do not have enough stock in the warehouse %s",
                                    product_id.name,
                                    warehouse_id_pos.name,
                                ),
                            }
                        )
                        return data
                    products_name += f"{product_id.name} ,"

        if products_name and not sell_kit_from_another_store:
            data.update(
                {
                    "msg_error": _(
                        "The product's '%s' not available in stock warehouse %s",
                        products_name,
                        warehouse_id_pos.name,
                    ),
                }
            )

        return data
    
