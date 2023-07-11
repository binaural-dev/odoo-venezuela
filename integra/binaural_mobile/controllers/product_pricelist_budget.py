import logging
import json

from odoo import _, http
from odoo.http import request
from odoo.osv import expression
from . import utils

_logger = logging.getLogger(__name__)


class ProductPricelistBudget(http.Controller):
    @http.route(
        "/budget/product_pricelist",
        type="http",
        methods=["GET"],
        auth="public",
        website=False,
        sitemap=False,
    )
    def get_product_pricelist(self, product_id, partner_id):
        data = {"status": 200, "msg": _("Success")}
        price = 0
        try:
            partner = utils.browse_model_data("res.partner", int(partner_id))
            pricelist = partner.property_product_pricelist
            product = utils.browse_model_data("product.product", int(product_id))

            if pricelist.active:
                price = pricelist.price_get(product.id, 1, partner)
                price = price.get(list(price.keys())[0])
            data.update({"data": price})
        except Exception as e:
            data.update(
                {"status": 409, "msg": _("The request couldn't be complete due a source conflict.")}
            )

        return json.dumps(data)
