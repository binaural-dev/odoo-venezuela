import json

from odoo import http, _
from odoo.http import request
from .utils import get_model_count, get_model_data, get_search_domain, browse_model_data
from ...tools import binaural_cne_query

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
    "display_name",
]
CHILDFIELDNAMES = ["street", "id", "type"]
CHILD_TYPES = ["invoice", "delivery"]
FIELDFILTERS = ["id", "name", "seller_id"]

class ResPartnerBudget(http.Controller):
    
    @http.route(['/budget','/budget-<int:budget_id>'], type='http', auth="user", website=True, csrf=False)
    def portal_budget(self, budget_id=False, **kw):
        user = request.env.user
        if user.employee_id.is_seller:
            edit_fee = False
            create_client = False
            price_lists = False
            budget = False
            symbol_currency = request.env.company.currency_id

            for group in user.groups_id:
                if group.name == "Portal / Vendedores que puedan editar tarifas":
                    edit_fee = True
                    price_lists = request.env["product.pricelist"].sudo().search([("selectable", "=" , True), ("active", "=", True)])
                if group.name == "Portal / Vendedores que puedan crear contactos":
                    create_client = True
            
            type_document = request.env['res.partner']._fields['prefix_vat'].selection
            country_ids = request.env["res.country"].search([])

            if budget_id:
                budget = request.env["sale.order"].search([("id", "=", budget_id)])

            return request.render("binaural_mobile.portal_budget_form", {
                "budget": budget,
                "currency": symbol_currency,
                "edit_fee": edit_fee,
                "create_client": create_client,
                "pricelists": price_lists,
                "quotation": True,
                "no_footer":True,
                "type_document": type_document,
                "countries": country_ids,
            })
        return request.redirect("/my/home")
    
    @http.route(['/budget/client'], type='http', auth="public", methods=['GET'], website=True, sitemap=False)
    def get_clients(self, query="", **kw):
        data = {"status": 200, "msg": "OK", "data": False}
        seller_portal_id = request.env.user.employee_id.id
        domain = [
            ('name', '=ilike', "%" + (query or '') + "%"),
            ('seller_ids', '=', seller_portal_id),
            ('is_public', '=', True),
            ("type", "=", "contact")
            ]
        partners = get_model_data("res.partner", domain, FIELDNAMES)

        if not partners:
            data.update(
                {"status": 404, 
                "msg": _("not found clients"),
                })
            return json.dumps(data)

        for partner in partners:
            partner.update({"child_ids": self.parse_child_ids(partner.get("child_ids"))})
        
        data.update({
            "data": partners,
        })
        return request.make_response(
            json.dumps(data),
            headers=[("Content-Type", "application/json")]
        )
    
    @staticmethod
    def parse_child_ids(child_ids):
        if not child_ids:
            return []
        
        domain = [("id", "in", child_ids), ("type", "in", CHILD_TYPES)]
        partner_child = get_model_data("res.partner", domain, CHILDFIELDNAMES)
        return partner_child
    
    @http.route(
        "/budget/create_client", type="json", methods=["POST"], auth="public", website=False, sitemap=False
    )
    def create_client(
        self, prefix=None, 
        vat='', country=None, 
        street='', name='', 
        email='', number='', 
        state=False, municipality=False, 
        parish=False, **kwargs
        ):
        
        data = {"status": 200, "msg": _("Success")}
        try:
            if prefix and vat and street and name:
                exist_partner = request.env["res.partner"].search(
                    [
                        ("vat", "=", vat),("prefix_vat", "=", prefix)
                    ]
                )
                if exist_partner:
                    data.update({"status": 409, "msg": _("This customer is already registered with another seller")})
                    return data
                
                created_partner = request.env["res.partner"].create({
                    "name": name,
                    "prefix_vat": prefix,
                    "vat": vat,
                    "street": street,
                    "country_id": country,
                    "state_id": state,
                    "municipality": municipality,
                    # "parish": parish,
                    "email": email,
                    "phone": number,
                    "type": "contact",
                    "is_public":True,
                    "seller_ids": request.env.user.employee_id,
                })
                
                return data
        except Exception as e:
            data.update({"status": 400, "msg": str(e)})
            return data

    @http.route(
        "/budget/get_name_client", type="json", methods=["POST"], auth="public", website=False, sitemap=False
    )
    def get_name_client(self, prefix=None, vat='', **kwargs):
        
        data = {"status": 200, "msg": _("Success")}
        try:
            if prefix and vat:
                name, flag = binaural_cne_query.get_default_name_by_vat(self, prefix, vat)
                if not flag:
                    data.update({"status": 400, "msg": _("No found vat in CNE")})
                    return data
                data.update({"data": name})
                return data
        except Exception as e:
            data.update({"status": 400, "msg": str(e)})
            return data
        
    @http.route('/budget/search_filter', type='http', auth="public", methods=['GET'], website=True, sitemap=False)
    def search_filter_country_state(self, **kw):
        models_allowed = {
        "2": "res.country.state",
        "3": "res.country.municipality",
        "4": "res.country.parish",
        }
        model_name = kw.get('namemodel')
        if model_name not in models_allowed.keys():
            return request.not_found()
        
        data = request.env[models_allowed[model_name]].search_read(
            domain=[(kw.get('ref'), '=', int(kw.get('filter')))],
            fields=['id', kw.get('field')],
        )
        return request.make_response(
            json.dumps(data),
            headers=[("Content-Type", "application/json")]
        )