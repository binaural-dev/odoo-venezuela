import logging

from dateutil.relativedelta import relativedelta
from odoo import _, fields, http
from odoo.addons.binaural_mobile.controllers.account_move_payments import (
    AccountMovePayments,
    FIELDPARTNER,
    FIELDNAMES,
    FIELDFILTERS
)
from odoo.http import request
from odoo.osv import expression
from odoo.tools import float_is_zero

_logger = logging.getLogger(__name__)

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

        partner_ids = request.env["res.partner"].sudo().search([("id", "=", int(partner_id))])
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

        order_options = {"0": "create_date asc", "1": "amount_residual desc"}

        order_invoices = order_options.get(request.env.company.order_payment, "create_date asc")

        account_move_ids = (
            request.env["account.move"].sudo().search(domain=domain, order=order_invoices)
        )

        acc_move_count = len(account_move_ids)
        all_acc_move_count = len(account_move_ids)
        account_move_results = []
        lang = request.env["res.lang"].sudo().search([("code", "=", request.env.user.lang)])
        date_format = lang.date_format if lang else "%Y-%m-%d"

        if acc_move_count > 0:
            currency_foreign_id = request.env.company.currency_foreign_id
            journal_id = account_move_ids[0].journal_id
            for account_move_id in account_move_ids:
                account_move_result_lines_with_residual_amount = account_move_id.line_ids.filtered(
                    lambda l: not float_is_zero(
                        l.amount_residual, precision_rounding=l.currency_id.rounding
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

                account_move_result[
                    "line_ids"
                ] = account_move_result_lines_with_residual_amount.read(
                    ["amount_residual", "date_maturity"]
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
            data.update({"status": 204, "msg": "Factura no encontrada", "count": 0, "data": False})

        return data
