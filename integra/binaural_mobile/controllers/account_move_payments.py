import json
import logging
from datetime import datetime
from pprint import pprint

from dateutil.relativedelta import relativedelta
from odoo import _, fields, http
from odoo.http import request
from odoo.osv import expression
from odoo.tools import float_is_zero

from . import utils

_logger = logging.getLogger(__name__)

FIELDPARTNER = [
    "id",
    "name",
    "credit_limit",
    "total_due",
    "street",
    "street2",
    "city",
    "state_id",
    "zip",
    "parent_id",
    "seller_ids",
    "country_id",
    "active",
    "seller_ids",
    "total_due",
    "withholding_type_id",
    "display_name",
    "taxpayer_type",
]
FIELDNAMES = [
    "id",
    "name",
    "partner_id",
    "invoice_date",
    "invoice_date_due",
    "invoice_origin",
    "amount_untaxed",
    "amount_total",
    "amount_residual",
    "amount_tax",
    "state",
    "payment_state",
    "journal_id",
    "foreign_rate",
    "currency_id",
    "foreign_taxable_income",
    "foreign_total_billed",
    "line_ids",
]
FIELDFILTERS = ["id", "partner_id", "state"]


class AccountMovePayments(http.Controller):
    @http.route(
        ["/payments/client"],
        type="http",
        auth="public",
        methods=["GET"],
        website=True,
        sitemap=False,
    )
    def get_clients(self, query="", **kw):
        data = {"status": 200, "msg": "OK", "data": False}
        seller_portal_id = request.env.user.employee_id.id

        common_domain = [
            ("is_public", "=", True),
            ("type", "=", "contact"),
        ]

        if not request.env.user.has_group("binaural_mobile.group_sellers_show_all_client"):
            common_domain += [('seller_ids', '=', seller_portal_id)]

        domain_name = common_domain + [("name", "=ilike", "%" + (query or "") + "%")]
        domain_vat = common_domain + [("vat", "=ilike", "%" + (query or "") + "%")]

        domain = expression.OR([domain_name, domain_vat])

        partners = utils.get_model_data("res.partner", domain, FIELDPARTNER)

        if not partners:
            data.update({"status": 404, "msg": _("not found clients")})
            return json.dumps(data)

        module_advance_payment = (
            request.env["ir.module.module"]
            .sudo()
            .search([("name", "ilike", "binaural_advance_payment")], limit=1)
        )
        advance_payment_installed = module_advance_payment.state == "installed"
        if advance_payment_installed:
            advance_customer_id = request.env.company.advance_customer_account_id.id

            for partner in partners:
                domain_customer = [
                    ("partner_id", "=", partner.get("id")),
                    ("account_id", "=", advance_customer_id),
                    ("move_id.state", "=", "posted"),
                ]

                advance_lines = request.env["account.move.line"].search(domain_customer)

                credit_partner = 0

                for line in advance_lines:
                    credit_partner += line.filtered(lambda l: not l.reconciled).amount_residual

                partner["credit_partner"] = credit_partner
        else:
            for partner in partners:

                partner["credit_partner"] = 0

        data.update(
            {
                "data": partners,
            }
        )
        return request.make_response(
            json.dumps(data), headers=[("Content-Type", "application/json")]
        )

    @http.route("/payments/account_move", type="json", auth="public", website=False, sitemap=False)
    def app_account_move_movil(
        self, limit=100, offset=100, partner_id=None, type_dairy=None, **kwargs
    ):
        """
        This function is used to obtain all the invoices or sales notes of the client and the journal selected in invoice payments.

        Args:
            partner_id (int, optional): partner selected in payment APP. Defaults to None.
            type_dairy (int, optional): dairy selected in payment APP. Defaults to None.

        Returns:
            data: invoices results
        """
        data = {"status": 200, "msg": "Success"}

        try:
            seller_id = request.env.user

            partner_ids = request.env["res.partner"].search([("id", "=", int(partner_id))])
            partner_ids += partner_ids.child_ids

            domain = [
                ("partner_id", "in", partner_ids.ids),
                ("payment_state", "in", ["not_paid", "partial"]),
                ("move_type", "=", "out_invoice"),
                ("state", "=", "posted"),
                ("seller_id", "=", seller_id.employee_id.id),
                ("journal_id", "=", int(type_dairy)),
            ]

            order_options = {"0": "create_date asc", "1": "amount_residual desc"}

            order_invoices = order_options.get(request.env.company.order_payment, "create_date asc")

            account_move_ids = (
                request.env["account.move"].sudo().search(domain=domain, order=order_invoices)
            )

            acc_move_count = len(account_move_ids)
            all_acc_move_count = len(account_move_ids)
            account_move_results = []
            lang = request.env["res.lang"].search([("code", "=", request.env.user.lang)])
            date_format = lang.date_format if lang else "%Y-%m-%d"

            if acc_move_count > 0:
                currency_foreign_id = request.env.company.currency_foreign_id
                journal_id = account_move_ids[0].journal_id
                for account_move_id in account_move_ids:
                    account_move_result_lines_with_residual_amount = (
                        account_move_id.line_ids.filtered(
                            lambda l: not float_is_zero(
                                l.amount_residual, precision_rounding=l.currency_id.rounding
                            )
                        )
                    )

                    account_move_result = account_move_id.read(FIELDNAMES)[0]

                    account_move_result["journal_id"] = (
                        journal_id.name,
                        journal_id.id,
                        journal_id.fiscal,
                    )
                    account_move_result["is_foreign"] = True

                    if account_move_id.currency_id.id != currency_foreign_id.id:
                        account_move_result["currency_foreign"] = currency_foreign_id.symbol
                        account_move_result["is_foreign"] = False

                    account_move_result["line_ids"] = (
                        account_move_result_lines_with_residual_amount.read(
                            ["amount_residual", "date_maturity"]
                        )
                    )
                    for line in account_move_result["line_ids"]:

                        if not line.get("date_maturity", False):
                            continue

                        line["date_maturity"] = line["date_maturity"].strftime(date_format)

                    account_move_results.append(account_move_result)

                data.update(
                    {
                        "data": account_move_results,
                        "count": acc_move_count,
                        "total_count": all_acc_move_count,
                        "taxpayer_type": partner_ids[0].taxpayer_type,
                    }
                )

            else:
                data.update(
                    {"status": 204, "msg": "Factura no encontrada", "count": 0, "data": False}
                )

        except Exception as e:
            data.update({"status": 400, "msg": str(e)})

        return data

    @http.route(
        "/payments/get_symbol_currency", type="json", auth="public", website=False, sitemap=False
    )
    def get_symbol_currency(self, limit=100, offset=100, dairy_id=False, **kwargs):
        data = {"status": 200, "msg": "Success"}
        if not dairy_id:
            data.update({"status": 404, "msg": _("not found clients")})
            return data

        dairy = request.env["account.journal"].search([("id", "=", int(dairy_id))])
        dairy_with_igtf = False

        if kwargs["exist_igtf"]:
            dairy_with_igtf = dairy.is_igtf

        dairy_symbol = [
            dairy.currency_id.id,
            dairy.currency_id.symbol,
            dairy.currency_id.position,
            True if dairy_with_igtf else False,
        ]
        data.update({"data": dairy_symbol})
        return data

    @http.route(
        "/payments/convert_currency", type="json", auth="public", website=False, sitemap=False
    )
    def convert_currency(self, currency=False, amount=False, **kwargs):
        data = {"status": 200, "msg": "Success"}
        if not currency and not amount:
            data.update({"status": 404, "msg": _("not found currency")})
            return data

        currency_company = (request.env["res.currency"].search([("id", "=", int(currency))])).rate
        currency_converted = float(amount) / currency_company
        data.update({"data": currency_converted})
        return data

    @http.route(
        "/payments/get_currency_rate", type="json", auth="public", website=False, sitemap=False
    )
    def get_currency_rate(self, date_pay=False, **kwargs):
        data = {"status": 200, "msg": "Success"}
        if not date_pay:
            data.update({"status": 404, "msg": _("not found rate")})
            return data

        currency = request.env.company.currency_foreign_id.id
        company_id = request.env.company.id
        pay_day_formatted = datetime.strptime(date_pay, "%Y-%m-%d")
        currency_company = request.env["res.currency.rate"].search(
            [
                ("currency_id", "=", int(currency)),
                ("name", "<=", pay_day_formatted),
                ("company_id", "=", company_id),
            ],
            order="name desc",
            limit=1,
        )

        data.update({"data": [currency_company.rate, currency_company.inverse_company_rate]})

        return data

    @http.route(
        "/payments/get_value_igtf", type="json", auth="public", website=False, sitemap=False
    )
    def get_value_igtf(self, **kwargs):
        data = {"status": 200, "msg": "Success"}

        if request.env.company.module_binaural_igtf:
            percentage = request.env.company.igtf_percentage
            if percentage:
                data.update({"data": percentage})
                return data

        data.update({"status": 404, "msg": _("IGTF OFF or not percentage configured")})

        return data