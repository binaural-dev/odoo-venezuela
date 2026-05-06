from odoo import api, fields, models, _
from odoo.tools import float_is_zero
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

    def _get_foreign_debit_credit_vals(self, foreign_amount):
        return {
            "foreign_debit": abs(foreign_amount) if foreign_amount < 0 else 0,
            "foreign_credit": abs(foreign_amount) if foreign_amount > 0 else 0,
        }

    def _get_receivable_account_id(self, accounting_partner, order):
        return accounting_partner.with_company(order.company_id).property_account_receivable_id.id

    def _create_payment_move(self, payment, order, payment_method, journal):
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
        payment.write({"account_move_id": payment_move.id})
        return payment_move

    def _build_credit_line_without_igtf(self, pos_session, payment_move, account_id, partner_id, amounts, payment):
        return pos_session._credit_amounts(
            {
                "account_id": account_id,
                "partner_id": partner_id,
                "move_id": payment_move.id,
                "not_foreign_recalculate": True,
                **self._get_foreign_debit_credit_vals(payment.foreign_amount),
            },
            amounts["amount"],
            amounts["amount_converted"],
        )

    def _build_credit_line_igtf(self, pos_session, payment_move, partner_id, payment, amount_igtf):
        return pos_session._credit_amounts(
            {
                "account_id": self.env.company.customer_account_igtf_id.id,
                "partner_id": partner_id,
                "move_id": payment_move.id,
                "not_foreign_recalculate": True,
                **self._get_foreign_debit_credit_vals(payment.foreign_igtf_amount),
            },
            amount_igtf,
            amount_igtf,
        )

    def _build_credit_line_igtf_base(self, pos_session, payment_move, account_id, partner_id, amounts, amount_igtf, payment):
        amount_without_igtf = float_round(
            payment.foreign_amount - payment.foreign_igtf_amount,
            precision_rounding=payment.currency_id.rounding,
        )
        return pos_session._credit_amounts(
            {
                "account_id": account_id,
                "partner_id": partner_id,
                "move_id": payment_move.id,
                "not_foreign_recalculate": True,
                **self._get_foreign_debit_credit_vals(amount_without_igtf),
            },
            amounts["amount"] - amount_igtf,
            amounts["amount_converted"] - amount_igtf,
        )

    def _get_reversed_move_receivable_account_id(self, payment, accounting_partner, order, is_reverse):
        is_split_transaction = payment.payment_method_id.split_transactions
        if is_split_transaction and is_reverse:
            account_id = self._get_receivable_account_id(accounting_partner, order)
        elif is_reverse:
            account_id = (
                payment.payment_method_id.receivable_account_id.id
                or self.company_id.account_default_pos_receivable_account_id.id
            )
        else:
            account_id = self.company_id.account_default_pos_receivable_account_id.id
        return account_id, is_split_transaction

    def _build_debit_line(self, pos_session, payment_move, account_id, accounting_partner, is_split_transaction, is_reverse, amounts, payment):
        return pos_session._debit_amounts(
            {
                "account_id": account_id,
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

    def _create_payment_moves(self, is_reverse=False):
        result = self.env["account.move"]

        for payment in self:
            order = payment.pos_order_id
            _logger.warning(" pago foraneo: %s", payment.foreign_amount)
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
            payment_move = self._create_payment_move(payment, order, payment_method, journal)
            result |= payment_move

            amounts = pos_session._update_amounts(
                {"amount": 0, "amount_converted": 0},
                {"amount": payment.amount},
                payment.payment_date,
            )

            amount_igtf = float_round(
                payment.igtf_amount,
                precision_rounding=payment.currency_id.rounding,
            )

            receivable_account_id = self._get_receivable_account_id(accounting_partner, order)

            if payment.include_igtf:
                # Keep the original behavior: only add base line when net amount is not exactly zero.
                if not (amounts["amount"] - amount_igtf == 0):
                    add_credit_line_vals = self._build_credit_line_igtf_base(
                        pos_session=pos_session,
                        payment_move=payment_move,
                        account_id=receivable_account_id,
                        partner_id=accounting_partner.id,
                        amounts=amounts,
                        amount_igtf=amount_igtf,
                        payment=payment,
                    )

                credit_line_vals = self._build_credit_line_igtf(
                    pos_session=pos_session,
                    payment_move=payment_move,
                    partner_id=accounting_partner.id,
                    payment=payment,
                    amount_igtf=amount_igtf,
                )
            else:
                credit_line_vals = self._build_credit_line_without_igtf(
                    pos_session=pos_session,
                    payment_move=payment_move,
                    account_id=receivable_account_id,
                    partner_id=accounting_partner.id,
                    amounts=amounts,
                    payment=payment,
                )

            reversed_move_receivable_account_id, is_split_transaction = self._get_reversed_move_receivable_account_id(
                payment=payment,
                accounting_partner=accounting_partner,
                order=order,
                is_reverse=is_reverse,
            )

            debit_line_vals = self._build_debit_line(
                pos_session=pos_session,
                payment_move=payment_move,
                account_id=reversed_move_receivable_account_id,
                accounting_partner=accounting_partner,
                is_split_transaction=is_split_transaction,
                is_reverse=is_reverse,
                amounts=amounts,
                payment=payment,
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
