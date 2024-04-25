from odoo import api, fields, models, _
from odoo.tools import formatLang, float_is_zero, float_compare
from odoo.tools.float_utils import float_round

import logging

_logger = logging.getLogger(__name__)


class PosPayment(models.Model):
    _inherit = "pos.payment"

    include_igtf = fields.Boolean()
    igtf_amount = fields.Float()
    foreign_igtf_amount = fields.Float()

    def _export_for_ui(self, payment):
        res = super()._export_for_ui(payment)
        res["include_igtf"] = payment.include_igtf
        res["igtf_amount"] = payment.igtf_amount
        res["foreign_igtf_amount"] = payment.foreign_igtf_amount
        return res

    def _create_payment_moves(self, is_reverse=False):
        result = self.env["account.move"]
        for payment in self:
            order = payment.pos_order_id
            add_credit_line_vals = False
            payment_method = payment.payment_method_id
            if payment_method.type == "pay_later" or float_is_zero(
                payment.amount, precision_rounding=order.currency_id.rounding
            ):
                continue
            accounting_partner = self.env["res.partner"]._find_accounting_partner(
                payment.partner_id
            )
            pos_session = order.session_id
            journal = pos_session.config_id.journal_id
            payment_move = (
                self.env["account.move"]
                .with_context(default_journal_id=journal.id)
                .create(
                    {
                        "journal_id": journal.id,
                        "date": fields.Date.context_today(order, order.date_order),
                        "ref": _("Invoice payment for %s (%s) using %s")
                        % (order.name, order.account_move.name, payment_method.name),
                        "pos_payment_ids": payment.ids,
                    }
                )
            )
            result |= payment_move
            payment.write({"account_move_id": payment_move.id})
            amounts = pos_session._update_amounts(
                {"amount": 0, "amount_converted": 0},
                {"amount": payment.amount},
                payment.payment_date,
            )
            amount_igtf = float_round(
                payment.igtf_amount,
                precision_rounding=payment.currency_id.rounding,
            )
            if payment.include_igtf:
                if not (amounts["amount"] - amount_igtf == 0):
                    amount_without_igtf = float_round(
                        payment.foreign_amount - payment.foreign_igtf_amount,
                        precision_rounding=payment.currency_id.rounding,
                    )
                    add_credit_line_vals = pos_session._credit_amounts(
                        {
                            "account_id": accounting_partner.with_company(
                                order.company_id
                            ).property_account_receivable_id.id,
                            "partner_id": accounting_partner.id,
                            "move_id": payment_move.id,
                            "not_foreign_recalculate": True,
                            "foreign_debit": abs(amount_without_igtf)
                            if amount_without_igtf < 0
                            else 0,
                            "foreign_credit": abs(amount_without_igtf)
                            if amount_without_igtf > 0
                            else 0,
                        },
                        amounts["amount"] - amount_igtf,
                        amounts["amount_converted"] - amount_igtf,
                    )

                credit_line_vals = pos_session._credit_amounts(
                    {
                        "account_id": self.env.company.customer_account_igtf_id.id,
                        "partner_id": accounting_partner.id,
                        "move_id": payment_move.id,
                        "not_foreign_recalculate": True,
                        "foreign_debit": abs(payment.foreign_igtf_amount)
                        if payment.foreign_igtf_amount < 0
                        else 0,
                        "foreign_credit": abs(payment.foreign_igtf_amount)
                        if payment.foreign_igtf_amount > 0
                        else 0,
                    },
                    amount_igtf,
                    amount_igtf,
                )
            else:
                credit_line_vals = pos_session._credit_amounts(
                    {
                        "account_id": accounting_partner.with_company(
                            order.company_id
                        ).property_account_receivable_id.id,  # The field being company dependant, we need to make sure the right value is received.
                        "partner_id": accounting_partner.id,
                        "move_id": payment_move.id,
                        "not_foreign_recalculate": True,
                        "foreign_debit": abs(payment.foreign_amount)
                        if payment.foreign_amount < 0
                        else 0,
                        "foreign_credit": abs(payment.foreign_amount)
                        if payment.foreign_amount > 0
                        else 0,
                    },
                    amounts["amount"],
                    amounts["amount_converted"],
                )

            is_split_transaction = payment.payment_method_id.split_transactions
            if is_split_transaction and is_reverse:
                reversed_move_receivable_account_id = accounting_partner.with_company(
                    order.company_id
                ).property_account_receivable_id.id
            elif is_reverse:
                reversed_move_receivable_account_id = (
                    payment.payment_method_id.receivable_account_id.id
                    or self.company_id.account_default_pos_receivable_account_id.id
                )
            else:
                reversed_move_receivable_account_id = (
                    self.company_id.account_default_pos_receivable_account_id.id
                )
            debit_line_vals = pos_session._debit_amounts(
                {
                    "account_id": reversed_move_receivable_account_id,
                    "move_id": payment_move.id,
                    "partner_id": accounting_partner.id
                    if is_split_transaction and is_reverse
                    else False,
                    "not_foreign_recalculate": True,
                    "foreign_debit": abs(payment.foreign_amount)
                    if payment.foreign_amount > 0
                    else 0,
                    "foreign_credit": abs(payment.foreign_amount)
                    if payment.foreign_amount < 0
                    else 0,
                },
                amounts["amount"],
                amounts["amount_converted"],
            )

            if add_credit_line_vals:
                self.env["account.move.line"].with_context(check_move_validity=False).create(
                    [add_credit_line_vals]
                )

            self.env["account.move.line"].with_context(check_move_validity=False).create(
                [credit_line_vals, debit_line_vals]
            )
            payment_move._post()
        return result
