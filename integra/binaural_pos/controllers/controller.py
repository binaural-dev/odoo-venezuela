import logging
import json

from odoo import http, _
from odoo.http import request
from odoo.osv import expression

_logger = logging.getLogger(__name__)

class ValidateQtyProducts(http.Controller):
    @http.route("/validate_products_order", type="json", auth="public", website=False, sitemap=False)
    def validate_products_order(
        self, line, qty, **kwargs
    ):
        if line:
            product_id = request.env['product.product'].search([('id', '=', line)]).product_tmpl_id
            data = {"status": 200, "msg": "Success"}
            if (
                product_id.detailed_type == "product"
                and product_id.qty_available < qty
            ):
                can_sell = False
                data.update(
                    {
                        "can_sell": can_sell,
                    }
                )
                return data
            data.update(
                {
                    "can_sell": True,
                }
            )

            return data
