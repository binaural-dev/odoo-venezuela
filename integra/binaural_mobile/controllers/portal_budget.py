import json

from odoo import http, _
from odoo.http import request
from .utils import get_model_count, get_model_data, get_search_domain, browse_model_data

import logging

_logger = logging.getLogger(__name__)

FIELDNAMES = [
    "id",
    "name",
    "credit_limit",
    "total_due",
    "street",
    "street2",
    "city",
    "state_id",
    "zip",
    "seller_id",
    "country_id",
    "property_product_pricelist",
    "property_payment_term_id",
    "type",
    "child_ids",
    "active",
    "seller_id",
    "property_payment_term_id",
]
CHILD_TYPES = ["invoice", "delivery"]
FIELDFILTERS = ["id", "name", "seller_id"]

class PortalBudget(http.Controller):
    
    @http.route(['/budget'], type='http', auth="user", website=True, csrf=False)
    def portal_budget(self, **kw):
        return request.render("binaural_mobile.portal_budget_form", {})
    
    @http.route(['/budget/client'], type='http', auth="public", methods=['GET'], website=True, sitemap=False)
    def get_clients(self, query="", **kw):
        data = {"status": 200, "msg": "OK"}
        seller_portal_id = request.env.user.employee_id.id
        domain = [
            ('name', '=ilike', (query or '') + "%"),
            ('seller_id', '=', seller_portal_id),
            ('is_public', '=', True),
            ("type", "=", "contact")
            ]
        data = get_model_data("res.partner", domain, FIELDFILTERS)

        if not data:
            data.update(
                {"status": 404, 
                "msg": _("not found clients")
                })
            return json.dumps(data)

        return request.make_response(
            json.dumps(data),
            headers=[("Content-Type", "application/json")]
        )
    
    @http.route("/budget/direction_client", type="json", auth="public", website=True, sitemap=False)
    def get_direction_client(self, **kw):
        data = {"status": 200, "msg": "OK"}

        domain = [
            ('parent_id', '=', int(kw.get("client"))),
            ('is_public', '=', True),
            ("type", "in", ["delivery", "invoice"])
            ]
        res_direction = get_model_data("res.partner", domain, ["street", "id", "type"])

        if not res_direction:
            data.update({"status": 404, "msg": _("not found direction in client")})
            return json.dumps(data)
        
        data.update({"data": res_direction})
        return json.dumps(data)