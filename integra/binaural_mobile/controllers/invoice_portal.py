import logging
import json

from odoo import _, http
from odoo.http import request
from odoo.osv import expression
from odoo.addons.account.controllers.portal import PortalAccount
from . import utils

_logger = logging.getLogger(__name__)

FIELDINVOICE = ["product_id", "price_subtotal", "tax_ids"]
MOVETYPES = [
    "out_invoice",
    "out_refund",
    "in_invoice",
    "in_refund",
    "out_receipt",
    "in_receipt",
]


class PortalAccount(PortalAccount):
    @http.route(
        ["/my/invoices", "/my/invoices/page/<int:page>"], type="http", auth="user", website=True
    )
    def portal_my_invoices(
        self, page=1, date_begin=None, date_end=None, sortby=None, filterby=None, **kw
    ):
        res = super(PortalAccount, self).portal_my_invoices(
            page=page,
            date_begin=date_begin,
            date_end=date_end,
            sortby=sortby,
            filterby=filterby,
            **kw
        )
        user_id = request.env.user
        if user_id.employee_id.is_seller:
            domain = [
                ("invoice_user_id", "=", user_id.id),
                ("state", "not in", ("cancel", "draft")),
                ("move_type", "in", MOVETYPES),
            ]

            domain = expression.OR(
                [
                    domain,
                    [
                        ("seller_id", "=", user_id.employee_id.id),
                        ("state", "not in", ("cancel", "draft")),
                        ("move_type", "in", MOVETYPES),
                    ],
                ]
            )

            invoices_count = request.env["account.move"].search_count(domain)
            pager = request.website.pager(
                url="/my/invoices",
                url_args={"date_begin": date_begin, "date_end": date_end},
                total=invoices_count,
                page=page,
                step=self._items_per_page,
            )

            AccountInvoice = request.env["account.move"]
            invoices = AccountInvoice.sudo().search(
                domain, order="name desc", limit=self._items_per_page, offset=pager["offset"]
            )
            request.session["my_invoices_history"] = invoices.ids[:100]
            is_seller = True
            res.qcontext.update(
                {
                    "invoices": invoices,
                    "pager": pager,
                    "default_url": "/my/invoices",
                    "is_seller": is_seller,
                }
            )
        return res

    @http.route(
        "/my/invoices/<int:invoice_id>/seller_invoice", type="http", auth="public", website=True
    )
    def portal_my_invoice_seller(self, invoice_id=None, access_token=None, **kw):
        user = request.env.user
        invoice = request.env["account.move"].sudo().browse(invoice_id)
        if not user.employee_id.is_seller or invoice.seller_id.id != user.employee_id.id:
            return request.redirect("/my/home")
        symbol_currency = request.env.company.currency_id

        return request.render(
            "binaural_mobile.portal_invoices_seller",
            {"currency": symbol_currency, "invoice": invoice, "no_footer": True},
        )

    @http.route("/get_tax_invoices", type="json", auth="public", website=True)
    def get_tax_invoices(self, invoice_id=None, **kw):
        data = {"status": 200, "msg": _("Success")}
        if not invoice_id:
            data.update(
                {
                    "status": 400,
                    "msg": _("Fail load invoice"),
                }
            )
            return data
        invoice_lines = (
            request.env["account.move.line"]
            .sudo()
            .search_read([("move_id", "=", int(invoice_id))], fields=FIELDINVOICE)
        )
        filtered_invoices = [invoice for invoice in invoice_lines if invoice["product_id"]]
        for line in filtered_invoices:
            description_tax = _("Tax no Selected")
            value_tax = 0
            if line["tax_ids"]:
                tax = request.env["account.tax"].search([("id", "=", line["tax_ids"][0])])
                value_tax = tax.amount
                description_tax = tax.description
            else:
                line["tax_ids"].append(0)
            line["tax_ids"].append(description_tax)
            line["tax_ids"].append(value_tax)
        data.update(
            {
                "data": filtered_invoices,
            }
        )
        return data
