import logging
import json

from odoo import _, http
from odoo.http import request
from odoo.osv import expression
from . import utils

_logger = logging.getLogger(__name__)
FIELDNAMES = ["id", "name", "active"]
FIELDFILTERS = ["id", "name"]


class ProductBrandBudget(http.Controller):
    @http.route("/budget/product_brand", type="http", methods=["GET"], auth="public", website=False, sitemap=False)
    def get_product_brand(self, limit=20, offset=0, **kwargs):
        data = {"status": 200, "msg": _("Success")}
        domain = expression.AND([[("active", "=", True)]])
        _filter = [key for key in FIELDFILTERS if kwargs.get(key)]

        if kwargs.get(FIELDFILTERS[1], False):
            search_domain = utils.get_search_domain(FIELDFILTERS[1], kwargs.get(FIELDFILTERS[1]))
            domain = expression.AND([domain, search_domain])
            _filter.remove(FIELDFILTERS[1])
        domain = expression.AND([domain, [(key, "=", int(kwargs.get(key))) for key in _filter]])

        brand_ids = utils.get_model_data(
            "product.brand", domain, FIELDNAMES, int(limit), int(offset)
        )
        all_brand_count = utils.get_model_count("product.brand", domain)
        brand_count = len(brand_ids)
        if not brand_count:
            data.update(
                {"status": 204, "msg": _("No brands were found"), "count": 0, "data": False}
            )
            return json.dumps(data)

        data.update({"data": brand_ids, "count": brand_count, "total_count": all_brand_count})
        return json.dumps(data)
