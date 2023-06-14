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
]
CHILDFIELDNAMES = ["street", "id", "type"]
CHILD_TYPES = ["invoice", "delivery"]
FIELDFILTERS = ["id", "name", "seller_id"]

class ResPartnerBudget(http.Controller):
    
    @http.route(['/budget'], type='http', auth="user", website=True, csrf=False)
    def portal_budget(self, **kw):
        if request.env.user.employee_id.is_seller:
            return request.render("binaural_mobile.portal_budget_form", {})
        return request.redirect("/my/home")
    
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
        partners = get_model_data("res.partner", domain, FIELDNAMES)

        if not partners:
            data.update(
                {"status": 404, 
                "msg": _("not found clients")
                })
            return json.dumps(data)

        for partner in partners:
            partner.update({"child_ids": self.parse_child_ids(partner.get("child_ids"))})

        return request.make_response(
            json.dumps(partners),
            headers=[("Content-Type", "application/json")]
        )
    
    @staticmethod
    def parse_child_ids(child_ids):
        if not child_ids:
            return []
        
        domain = [("id", "in", child_ids), ("type", "in", CHILD_TYPES)]
        partner_child = get_model_data("res.partner", domain, CHILDFIELDNAMES)
        return partner_child
