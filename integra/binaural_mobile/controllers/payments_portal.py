import logging
import json

from odoo import _, http
from odoo.http import request
from odoo.osv import expression
from . import utils

from odoo.addons.portal.controllers.portal import pager as payment_pager

_logger = logging.getLogger(__name__)
FIELDSDAIRY = ["id", "name", "company_id", "type"]


class PaymentsPortal(http.Controller):
    @http.route(
        ["/payment_list", "/payment_list/page/<int:page>"],
        type="http",
        auth="public",
        website=True,
        sitemap=False,
    )
    def payment_list(self, page=1, search=None, search_in="name", url="/payment_list", **kw):
        user_id = request.env.user
        if user_id.employee_id.is_seller:
            domain = [
                ("company_id", "=", request.env.company.id),
                ("seller_id", "=", user_id.employee_id.id),
                ("seller_id_user", "=", user_id.id),
            ]
            if search and search_in:
                domain = expression.AND(
                    [domain, self._get_search_domain_payments(search_in, search)]
                )
            _items_per_page = 25
            payment_mobile_count = request.env["payment.mobile"].sudo().search_count(domain)
            pager = payment_pager(
                url=url,
                url_args={
                    "search_in": search_in,
                    "search": search,
                },
                total=payment_mobile_count,
                page=page,
                step=_items_per_page,
            )
            payments = (
                request.env["payment.mobile"]
                .sudo()
                .search(domain, limit=_items_per_page, offset=pager["offset"])
            )
            return request.render(
                "binaural_mobile.payments_list_portal",
                {
                    "payments": payments,
                    "search": search,
                    "search_in": search_in,
                    "searchbar_inputs": self._get_searchbar_inputs_payments(),
                    "default_url": url,
                    "pager": pager,
                    "no_footer": True,
                    'show_create_payment_menuitem': True
                },
            )
        return request.redirect("/my/home")

    @http.route(
        "/payment_list/<int:invoice>", type="http", auth="public", website=True, sitemap=False
    )
    def payment_info(self, invoice=None, **kw):
        user_id = request.env.user
        if user_id.employee_id.is_seller:
            payments = (
                request.env["payment.mobile"]
                .sudo()
                .search(
                    [
                        ("company_id", "=", request.env.company.id),
                        ("id", "=", invoice),
                        ("seller_id", "=", user_id.employee_id.id),
                    ],
                )
            )
            payments_igtf = request.env['payment.mobile.igtf']
            lines = payments.payment_mobile_line
            for line in lines:
                payments_igtf += request.env['payment.mobile.igtf'].search([('payment_id', '=', line.payment_related.id )])

            return request.render(
                "binaural_mobile.payments_info_portal",
                {
                    "payments": payments,
                    "payment_registered": True,
                    "pay_igtf": payments_igtf,
                    "no_footer": True,
                    'show_create_payment_menuitem': True
                },
            )
        return request.redirect("/my/home")

    def _get_search_domain_payments(self, search_in, search):
        search_domain = []
        if search_in in ("name", "all"):
            search_domain = expression.OR([search_domain, [("partner_id.name", "ilike", search)]])
        return search_domain

    def _get_searchbar_inputs_payments(self):
        return {
            "name": {"input": "name", "label": _("Search for client")},
        }

    @http.route("/payments", type="http", auth="public", website=True, sitemap=False)
    def payments_portal(self, **kw):
        if request.env.user.employee_id.is_seller:
            dairy_payment = request.env.company.payment_methods_in_app
            dairy_sale = request.env.company.app_sales_diaries
            symbol_currency = request.env.company.currency_id
            foreign_currency = request.env.company.currency_foreign_id
            return request.render(
                "binaural_mobile.payments_portal_form",
                {
                    "dairy_sale": dairy_sale,
                    "dairy_payments": dairy_payment, 
                    "currency": symbol_currency,
                    "foreign_currency": foreign_currency,
                    "no_footer":True
                },
            )
        return request.redirect("/my/home")
    
    @http.route(
        "/payments/cancel_payment", type="json", auth="public", website=False, sitemap=False
    )
    def cancel_payment(self, payment=None ,**kwargs):
        data = {"status": 200, "msg": "Success"}
        if payment:
            payment_searched = request.env["payment.mobile"].search([("id", '=', int(payment))])
            if payment_searched.state not in 'cancel':
                payment_searched.cancel_payment()
            return data

        data.update({"status": 404, "msg": _("Not Found payment")})

        return data