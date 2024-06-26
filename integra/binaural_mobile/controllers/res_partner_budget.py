import json
import logging

from odoo import _, http
from odoo.http import request
from odoo.osv import expression

from ...tools import binaural_cne_query
from .utils import browse_model_data, get_model_count, get_model_data, get_search_domain

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
    "seller_ids",
    "country_id",
    "property_product_pricelist",
    "property_payment_term_id",
    "type",
    "child_ids",
    "active",
    "seller_ids",
    "display_name",
    "plus_code",
]
CHILDFIELDNAMES = ["street", "id", "type"]
CHILD_TYPES = ["invoice", "delivery"]
FIELDFILTERS = ["id", "name", "seller_ids"]

class ResPartnerBudget(http.Controller):

    def _get_tax_included(self, kwargs):
        company = request.env.company
        is_optional_tax_included = company.dairy_fiscal and company.dairy_no_fiscal

        if is_optional_tax_included:
            return kwargs.get("tax_included", False)

        return any(company.dairy_fiscal)
    
    @http.route(['/budget','/budget-<int:budget_id>'], type='http', auth="user", website=True, csrf=False)
    def portal_budget(self, budget_id=False, **kw):
        user = request.env.user
        if user.employee_id.is_seller:
            company = request.env.company
            edit_fee = False
            create_client = False
            create_client_address = False
            price_lists = False
            budget = False
            symbol_currency = request.env.company.currency_id
            is_optional_tax_included = company.dairy_fiscal and company.dairy_no_fiscal
            tax_included = self._get_tax_included(kw)

            for group in user.groups_id:
                if group.id == request.env.ref("binaural_mobile.group_sellers_edit_fee").id:
                    edit_fee = True
                    price_lists = request.env["product.pricelist"].sudo().search([("selectable", "=" , True), ("active", "=", True)])
                if group.id == request.env.ref("binaural_mobile.group_sellers_create_contact").id:
                    create_client = True
                if group.id == request.env.ref('binaural_mobile.group_sellers_create_contact_address').id:
                    create_client_address = True

            type_document = request.env['res.partner']._fields['prefix_vat'].selection
            country_ids = request.env["res.country"].search([])

            if budget_id:
                budget = request.env["sale.order"].search([("id", "=", budget_id)])
                tax_included = budget.tax_included

            return request.render("binaural_mobile.portal_budget_form", {
                "budget": budget,
                "currency": symbol_currency,
                "edit_fee": edit_fee,
                "create_client": create_client,
                "create_client_address": create_client_address,
                "pricelists": price_lists,
                "quotation": True,
                "no_footer":True,
                "type_document": type_document,
                "countries": country_ids,
                "not_confirm_quotes": user.has_group("binaural_mobile.group_sellers_cant_confirm_quotation"),
                "tax_included": tax_included,
                "is_optional_tax_included": is_optional_tax_included
            })
        return request.redirect("/my/home")
    
    @http.route(['/budget/client'], type='http', auth="public", methods=['GET'], website=True, sitemap=False)
    def get_clients(self, query="", **kw):
        data = {"status": 200, "msg": "OK", "data": False}
        seller_portal_id = request.env.user.employee_id.id
        common_domain = [
            ('is_public', '=', True),
            ("type", "=", "contact")
        ]

        if not request.env.user.has_group("binaural_mobile.group_sellers_show_all_client"):
            common_domain += [('seller_ids', '=', seller_portal_id)]

        domain_name = common_domain + [('name', '=ilike', "%" + (query or '') + "%")]
        domain_vat = common_domain + [('vat', '=ilike', "%" + (query or '') + "%")]

        domain = expression.OR([domain_name, domain_vat])
        
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
        parish=False, parent_id=False,
        city=False,
        plus_code='',
        type="contact", **kwargs
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
                    "city_id": city,
                    "municipality": municipality,
                    "email": email,
                    "phone": number,
                    "type": type,
                    "is_public":True,
                    "seller_ids": [request.env.user.employee_id.id],
                    "parent_id": parent_id,
                    "plus_code": plus_code,
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
        "5": "res.country.city",
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
