import logging

from dateutil.relativedelta import relativedelta
from odoo import _, fields, http
from odoo.addons.binaural_mobile.controllers.account_move_payments import (
    AccountMovePayments,
)
from odoo.http import request
from odoo.osv import expression

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
]
FIELDFILTERS = ["id", "partner_id", "state"]


class AccountMovePayments(AccountMovePayments):

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
        seller_id = request.env.user
        data = {"status": 200, "msg": "Success"}

        partner_ids = request.env["res.partner"].search([("id", "=", int(partner_id))])
        partner_ids += partner_ids.child_ids

        domain = [
            ("commission_invoice_date_field", "=", "invoice_reception_date"),
            ("invoice_reception_date", "!=", False),
        ]

        domain = expression.OR(
            [
                domain,
                [
                    ("commission_invoice_date_field", "!=", "invoice_reception_date"),
                ]
            ]
        )

        domain = expression.AND(
            [
                domain,
                [
                    ("partner_id", "in", partner_ids.ids),
                    ("payment_state", "in", ["not_paid", "partial"]),
                    ("move_type", "=", "out_invoice"),
                    ("state", "=", "posted"),
                    ("seller_id", "=", seller_id.employee_id.id),
                    ("journal_id", "=", int(type_dairy)),
                ],
            ]
        )

        today = fields.Date.context_today(seller_id)
        expired_date = fields.Date.from_string(today) - relativedelta(days=90)

        order_options = {"0": "create_date asc", "1": "amount_residual desc"}

        order_invoices = order_options.get(request.env.company.order_payment, "create_date asc")

        account_move_ids = (
            request.env["account.move"]
            .sudo()
            .search_read(domain=domain, fields=FIELDNAMES, order=order_invoices)
        )

        all_acc_move_count = (
            request.env["account.move"]
            .sudo()
            .search_read(domain=domain, fields=FIELDNAMES, order=order_invoices)
        )

        acc_move_count = len(account_move_ids)
        all_acc_move_count = len(all_acc_move_count)
        if acc_move_count > 0:
            currency_foreign_id = request.env.company.currency_foreign_id
            journal_id = account_move_ids[0].get("journal_id")
            fiscal = (
                request.env["account.journal"].sudo().search([("id", "=", journal_id[0])]).fiscal
            )
            for account_move_id in account_move_ids:

                account_move_id["journal_id"] = journal_id + (fiscal,)
                account_move_id["is_foreign"] = True

                if account_move_id.get("currency_id")[0] != currency_foreign_id.id:
                    account_move_id["currency_foreign"] = currency_foreign_id.symbol
                    account_move_id["is_foreign"] = False

            data.update(
                {
                    "data": account_move_ids,
                    "count": acc_move_count,
                    "total_count": all_acc_move_count,
                }
            )

        else:
            data.update({"status": 204, "msg": "Factura no encontrada", "count": 0, "data": False})

        return data
