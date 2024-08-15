import logging

from odoo import _, http, fields
from odoo.http import request, route
from odoo.osv import expression
from odoo.addons.sale.controllers.portal import CustomerPortal
from odoo.addons.portal.controllers.portal import pager as portal_pager
from odoo.addons.account.controllers.portal import PortalAccount
from collections import OrderedDict
from dateutil.relativedelta import relativedelta
from odoo.tools import date_utils

_logger = logging.getLogger(__name__)


class CustomerPortalInh(CustomerPortal):
    def _prepare_quotations_domain(self, partner):
        employee_id = request.env.user.employee_id
        domain = [
            ("message_partner_ids", "child_of", [partner.commercial_partner_id.id]),
            ("state", "in", ["sent", "cancel"]),
        ]
        if employee_id.is_seller:
            domain.append(("state", "in", ["sent", "cancel", "draft"]))
            domain.append(("seller_id", "=", employee_id.id))
        return domain

    def _prepare_orders_domain(self, partner):
        employee_id = request.env.user.employee_id
        domain = [
            ("message_partner_ids", "child_of", [partner.commercial_partner_id.id]),
            ("state", "in", ["sale", "done"]),
        ]
        if employee_id.is_seller:
            domain.append(("seller_id", "=", employee_id.id))
        return domain

    def _get_searchbar_inputs_payments(self):
        return {
            "name": {"input": "name", "label": _("Search for client")},
            "num": {"input": "num", "label": _("Search for Number")},
        }

    def _get_search_domain_payments(self, search_in, search):
        search_domain = []
        if search_in in ("name", "all"):
            search_domain = expression.OR([search_domain, [("partner_id.name", "ilike", search)]])
        if search_in in ("num", "all"):
            search_domain = expression.OR([search_domain, [("name", "ilike", search)]])
        return search_domain

    def _prepare_sale_portal_rendering_values(
        self, page=1, date_begin=None, date_end=None, sortby=None, quotation_page=False,search=None, search_in="name", filterby=None, **kwargs
    ):
        SaleOrder = request.env["sale.order"]

        if not sortby:
            sortby = "date"

        partner = request.env.user.partner_id
        values = self._prepare_portal_layout_values()

        if quotation_page:
            url = "/my/quotes"
            domain = self._prepare_quotations_domain(partner)
        else:
            url = "/my/orders"
            domain = self._prepare_orders_domain(partner)

        employee_id = request.env.user.employee_id

        searchbar_sortings = self._get_sale_searchbar_sortings()

        sort_order = searchbar_sortings[sortby]["order"]

        if date_begin and date_end:
            domain += [("create_date", ">", date_begin), ("create_date", "<=", date_end)]

        if search and search_in:
            domain = expression.AND([domain, self._get_search_domain_payments(search_in, search)])

        searchbar_filters = self.quotation_order_searchbar_filters()
        if not filterby:
            filterby = "all"
        domain = expression.AND([domain, searchbar_filters[filterby]["domain"]])

        _items_per_page = 25
        pager_values = portal_pager(
            url=url,
            total=SaleOrder.search_count(domain),
            page=page,
            step=_items_per_page,
            url_args={
                "date_begin": date_begin,
                "date_end": date_end,
                "sortby": sortby,
                "search_in": search_in,
                "search": search,
            },
        )
        orders = SaleOrder.search(
            domain, order=sort_order, limit=_items_per_page, offset=pager_values["offset"]
        )

        values.update(
            {
                "date": date_begin,
                "quotations": orders.sudo() if quotation_page else SaleOrder,
                "orders": orders.sudo() if not quotation_page else SaleOrder,
                "page_name": "quote" if quotation_page else "order",
                "pager": pager_values,
                "default_url": url,
                "searchbar_sortings": searchbar_sortings,
                "sortby": sortby,
                "search": search if employee_id.is_seller else False,
                "search_in": search_in if employee_id.is_seller else False,
                "searchbar_inputs": self._get_searchbar_inputs_payments()
                if employee_id.is_seller
                else False,
                "searchbar_filters": OrderedDict(sorted(searchbar_filters.items())),
                "filterby": filterby if employee_id.is_seller else False,
                "no_footer": True if employee_id.is_seller else False,
            }
        )

        return values

    def quotation_order_searchbar_filters(self):
        return {
            "all": {"label": _("All"), "domain": []},
            "invoices": {
                "label": _("Invoices"),
                "domain": [("state", "=", ("out_invoice", "out_refund"))],
            },
            "bills": {
                "label": _("Bills"),
                "domain": [("move_type", "=", ("in_invoice", "in_refund"))],
            },
        }

    @route(["/my", "/my/home"], type="http", auth="user", website=True)
    def home(self, **kw):
        res = super().home()
        res.qcontext.update(
            {"no_footer": True if request.env.user.employee_id.is_seller else False}
        )
        return res


class PortalAccountInh(PortalAccount):
    @http.route(
        ["/my/invoices", "/my/invoices/page/<int:page>"], type="http", auth="user", website=True
    )
    def portal_my_invoices(
        self,
        page=1,
        date_begin=None,
        date_end=None,
        sortby=None,
        filterby=None,
        search=None,
        search_in="name",
        **kw
    ):
        values = self._prepare_my_invoices_values(
            page, date_begin, date_end, sortby, filterby, search=search, search_in=search_in
        )

        pager = portal_pager(**values["pager"])

        invoices = values["invoices"](pager["offset"])
        request.session["my_invoices_history"] = invoices.ids[:100]

        values.update(
            {
                "invoices": invoices,
                "pager": pager,
            }
        )
        return request.render("account.portal_my_invoices", values)

    def _prepare_my_invoices_values(
        self,
        page,
        date_begin,
        date_end,
        sortby,
        filterby,
        search=None,
        search_in="name",
        domain=None,
        url="/my/invoices",
    ):
        values = self._prepare_portal_layout_values()
        AccountInvoice = request.env["account.move"]

        domain = expression.AND(
            [
                domain or [],
                self._get_invoices_domain(),
            ]
        )

        searchbar_sortings = self._get_account_searchbar_sortings()
        if not sortby:
            sortby = "date"
        order = searchbar_sortings[sortby]["order"]

        searchbar_filters = self._get_account_searchbar_filters()
        if not filterby:
            filterby = "a_all"
        if filterby not in (
            "d_next_installment_payment_date_this_month",
            "d_next_installment_payment_date_next_month",
        ):
            _logger.warning("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA")
            _logger.warning(searchbar_filters)
            _logger.warning(filterby)
            domain += searchbar_filters[filterby]["domain"]

        if search and search_in:
            domain = expression.AND(
                [domain, CustomerPortalInh._get_search_domain_payments(self, search_in, search)]
            )

        if date_begin and date_end:
            domain += [("create_date", ">", date_begin), ("create_date", "<=", date_end)]

        user_id = request.env.user

        _items_per_page = 25

        def search_invoice(pager_offset):
            today = fields.Date.today()
            next_month = today + relativedelta(months=1)
            invoices = AccountInvoice.search(
                domain, order=order, limit=_items_per_page, offset=pager_offset
            )
            if filterby == "d_next_installment_payment_date_this_month":
                res = invoices.filtered(
                    lambda i: i.next_installment_date
                    and i.next_installment_date >= today
                    and i.next_installment_date <= date_utils.end_of(today, "month")
                )
                return res
            if filterby == "d_next_installment_payment_date_next_month":
                res = invoices.filtered(
                    lambda i: i.next_installment_date
                    and i.next_installment_date >= date_utils.start_of(next_month, "month")
                    and i.next_installment_date <= date_utils.end_of(next_month, "month")
                )
                _logger.warning("RESSS: %s", res)
                return res
            return invoices

        values.update(
            {
                "date": date_begin,
                "invoices": search_invoice,
                "page_name": "invoice",
                "pager": {
                    "url": url,
                    "url_args": {"date_begin": date_begin, "date_end": date_end, "sortby": sortby},
                    "total": AccountInvoice.search_count(domain),
                    "page": page,
                    "step": _items_per_page,
                },
                "default_url": url,
                "searchbar_sortings": searchbar_sortings,
                "sortby": sortby,
                "searchbar_filters": OrderedDict(sorted(searchbar_filters.items())),
                "filterby": filterby,
                "search": search,
                "search_in": search_in,
                "searchbar_inputs": CustomerPortalInh._get_searchbar_inputs_payments(self)
                if user_id.employee_id.is_seller
                else False,
                "no_footer": True if user_id.employee_id.is_seller else False,
            }
        )
        return values

    def _get_invoices_domain(self, m_type=None):
        if m_type in ['in', 'out']:
            move_type = [m_type+move for move in ('_invoice', '_refund', '_receipt')]
        else:
            domain = [
                ("state", "not in", ("cancel", "draft")),
            ]
            user_id = request.env.user

            if user_id.employee_id.is_seller:
                domain = expression.AND(
                    [
                        domain,
                        [("seller_id", "=", user_id.employee_id.id), ("move_type", "=", "out_invoice")],
                    ]
                )
            else:
                domain = expression.AND(
                    [
                        domain,
                        [
                            ("partner_id", "=", user_id.id),
                            (
                                "move_type",
                                "in",
                                (
                                    "out_invoice",
                                    "out_refund",
                                    "in_invoice",
                                    "in_refund",
                                    "out_receipt",
                                    "in_receipt",
                                ),
                            ),
                        ],
                    ]
                )

        return domain

    def _get_account_searchbar_filters(self):
        user_id = request.env.user

        if user_id.employee_id.is_seller:
            today = fields.Date.today()
            quarter_start, quarter_end = date_utils.get_quarter(today)
            quarter_start_2, quarter_end_2 = date_utils.get_quarter(
                today + relativedelta(months=-4)
            )
            quarter_start_3, quarter_end_3 = date_utils.get_quarter(
                today + relativedelta(months=-8)
            )
            quarter_start_4, quarter_end_4 = date_utils.get_quarter(
                today + relativedelta(months=-12)
            )
            last_month = today + relativedelta(months=-1)
            last_2_month = today + relativedelta(months=-2)
            last_year = today + relativedelta(years=-1)
            last_2_year = today + relativedelta(years=-2)

            return {
                "a_all": {"label": _("Todo"), "domain": []},
                "a_nopaid": {"label": _("No Paid"), "domain": [("payment_state", "=", "not_paid")]},
                "a_paid": {"label": _("Paid"), "domain": [("payment_state", "=", "paid")]},
                "a_partial": {"label": _("Partial"), "domain": [("payment_state", "=", "partial")]},
                "b_month": {
                    "label": _("Este mes"),
                    "domain": [
                        ("create_date", ">=", date_utils.start_of(today, "month")),
                        ("create_date", "<=", date_utils.end_of(today, "month")),
                    ],
                },
                "b_month_2": {
                    "label": _("Mes pasado"),
                    "domain": [
                        ("create_date", ">=", date_utils.start_of(last_month, "month")),
                        ("create_date", "<=", date_utils.end_of(last_month, "month")),
                    ],
                },
                "b_month_3": {
                    "label": _("Mes antepasado"),
                    "domain": [
                        ("create_date", ">=", date_utils.start_of(last_2_month, "month")),
                        ("create_date", "<=", date_utils.end_of(last_2_month, "month")),
                    ],
                },
                "c_quarter": {
                    "label": _("Q1"),
                    "domain": [
                        ("create_date", ">=", quarter_start),
                        ("create_date", "<=", quarter_end),
                    ],
                },
                "c_quarter_2": {
                    "label": _("Q2"),
                    "domain": [
                        ("create_date", ">=", quarter_start_2),
                        ("create_date", "<=", quarter_end_2),
                    ],
                },
                "c_quarter_3": {
                    "label": _("Q3"),
                    "domain": [
                        ("create_date", ">=", quarter_start_3),
                        ("create_date", "<=", quarter_end_3),
                    ],
                },
                "c_quarter_4": {
                    "label": _("Q4"),
                    "domain": [
                        ("create_date", ">=", quarter_start_4),
                        ("create_date", "<=", quarter_end_4),
                    ],
                },
                "d_next_installment_payment_date_this_month": {
                    "label": _("La próxima cuota de pago es este mes"),
                },
                "d_next_installment_payment_date_next_month": {
                    "label": _("La próxima cuota de pago es el mes siguiente"),
                },
                "year": {
                    "label": _("Este año"),
                    "domain": [
                        ("create_date", ">=", date_utils.start_of(today, "year")),
                        ("create_date", "<=", date_utils.end_of(today, "year")),
                    ],
                },
                "year_last": {
                    "label": _("El año pasado"),
                    "domain": [
                        ("create_date", ">=", date_utils.start_of(last_year, "year")),
                        ("create_date", "<=", date_utils.end_of(last_year, "year")),
                    ],
                },
                "year_last_2": {
                    "label": _("El año antepasado"),
                    "domain": [
                        ("create_date", ">=", date_utils.start_of(last_2_year, "year")),
                        ("create_date", "<=", date_utils.end_of(last_2_year, "year")),
                    ],
                },
                "invoices": {
                    "label": _("Invoices"),
                    "domain": [("move_type", "in", ("out_invoice", "out_refund"))],
                },
            }
        return {
            "all": {"label": _("All"), "domain": []},
            "invoices": {
                "label": _("Invoices"),
                "domain": [("move_type", "in", ("out_invoice", "out_refund"))],
            },
            "bills": {
                "label": _("Bills"),
                "domain": [("move_type", "in", ("in_invoice", "in_refund"))],
            },
        }
