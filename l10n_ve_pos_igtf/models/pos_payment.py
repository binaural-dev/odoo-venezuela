from odoo import api, fields, models, _
from odoo.exceptions import UserError
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

    def _get_pos_receivable_account(self, accounting_partner, company):
        """Return the receivable account to use for a POS payment line.

        Falls back to the company's default POS receivable account when the
        partner has no ``property_account_receivable_id`` set in ``company``
        (e.g. a contact created on the fly from the POS). Without this
        fallback, ``_create_payment_moves`` tried to create an
        ``account.move.line`` with an empty ``account_id``, which PostgreSQL
        rejected via the ``account_move_line_check_accountable_required_fields``
        check constraint, aborting the whole transaction with a generic error.
        """
        account = accounting_partner.with_company(
            company
        ).property_account_receivable_id
        if not account:
            account = company.account_default_pos_receivable_account_id
        if not account:
            raise UserError(
                _(
                    "El cliente %(partner)s no tiene cuenta por cobrar "
                    "configurada en la compañía %(company)s, y la compañía "
                    "tampoco tiene una cuenta por cobrar por defecto de Punto "
                    "de Venta configurada.",
                    partner=accounting_partner.display_name,
                    company=company.display_name,
                )
            )
        return account

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
                        "ref": _(
                            "Invoice payment for %(order)s (%(invoice)s) using "
                            "%(method)s",
                            order=order.name,
                            invoice=order.account_move.name,
                            method=payment_method.name,
                        ),
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
            amount_igtf = payment.igtf_amount

            if payment.include_igtf:
                if not (amounts["amount"] - amount_igtf == 0):
                    add_credit_line_vals = pos_session._credit_amounts(
                        {
                            "account_id": self._get_pos_receivable_account(
                                accounting_partner, order.company_id
                            ).id,
                            "partner_id": accounting_partner.id,
                            "move_id": payment_move.id,
                        },
                        amounts["amount"] - amount_igtf,
                        amounts["amount_converted"] - amount_igtf,
                    )

                credit_line_vals = pos_session._credit_amounts(
                    {
                        "account_id": self.env.company.customer_account_igtf_id.id,
                        "partner_id": accounting_partner.id,
                        "move_id": payment_move.id,
                    },
                    amount_igtf,
                    amount_igtf,
                )
            else:
                credit_line_vals = pos_session._credit_amounts(
                    {
                        "account_id": self._get_pos_receivable_account(
                            accounting_partner, order.company_id
                        ).id,
                        "partner_id": accounting_partner.id,
                        "move_id": payment_move.id,
                    },
                    amounts["amount"],
                    amounts["amount_converted"],
                )

            is_split_transaction = payment.payment_method_id.split_transactions
            if is_reverse:
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
                },
                amounts["amount"],
                amounts["amount_converted"],
            )

            if add_credit_line_vals:
                receivable_line = self.env["account.move.line"].with_context(check_move_validity=False).create(
                    [add_credit_line_vals]
                )
                receivable_line.not_foreign_recalculate = True
                receivable_line.foreign_credit = abs(payment.foreign_amount - payment.foreign_igtf_amount)

            other_lines = self.env["account.move.line"].with_context(check_move_validity=False).create(
                [credit_line_vals, debit_line_vals]
            )
            igtf_or_receivable_line = other_lines[0]
            debit_line = other_lines[1]

            # Setear Bs correctos en la línea de débito (CUENTA POR COBRAR POS)
            debit_line.not_foreign_recalculate = True
            debit_line.foreign_debit = abs(payment.foreign_amount)

            # Setear Bs correctos en crédito IGTF o cuenta por cobrar (pago sin IGTF split)
            igtf_or_receivable_line.not_foreign_recalculate = True
            if payment.include_igtf:
                igtf_or_receivable_line.foreign_credit = abs(payment.foreign_igtf_amount)
            else:
                igtf_or_receivable_line.foreign_credit = abs(payment.foreign_amount)

            payment_move._post()
        return result
