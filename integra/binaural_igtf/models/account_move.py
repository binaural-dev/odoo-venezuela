from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class AccountMoveIgtf(models.Model):
    _inherit = "account.move"

    def default_is_igtf(self):
        return self.env.company.is_igtf or False

    default_is_igtf_config = fields.Boolean(default=default_is_igtf)

    payment_igtf_id = fields.Many2one(
        "account.payment",
        string="Payment IGTF",
        help="Payment IGTF",
        readonly=True,
        copy=False,
    )

    def recalculate_bi_igtf(self, line_id=None, initial_residual=0.0):
        """This method can be used by ir.actions.server to update bi_igtf"""
        for record in self:
            if not record.invoice_payments_widget:
                record.bi_igtf = 0
                continue

            payments = record.invoice_payments_widget.get("content", False)
            amount = 0
            if line_id:
                line = self.env["account.move.line"].browse([line_id])
                payment_id = line.move_id.payment_id
                if payment_id and payment_id.is_igtf_on_foreign_exchange:
                    payment_id = line.move_id.payment_id
                    bi_igtf = payment_id.get_bi_igtf()
                    if initial_residual < bi_igtf:
                        record.bi_igtf = initial_residual
                        continue
                    record.bi_igtf += bi_igtf
                    continue

            for payment in payments:
                payment_id = payment.get("account_payment_id", False)
                if not payment_id:
                    continue

                payment_id = record.env["account.payment"].browse([payment_id])
                if payment_id.is_igtf_on_foreign_exchange:
                    bi_igtf = payment_id.get_bi_igtf()
                    if initial_residual < bi_igtf:
                        record.bi_igtf = initial_residual
                        continue
                    amount += bi_igtf

            record.bi_igtf = amount

    def remove_igtf_from_move(self, partial_id):
        """Remove IGTF from move

        this method is called when a partial reconciliation is removed from the reconciliation widget
        search for the partial reconciliation and remove the IGTF from the move if it is a payment

        :param partial_id: id of the partial reconciliation to remove
        :type partial_id: int
        """

        partial = self.env["account.partial.reconcile"].browse(partial_id)

        payment_credit = partial.credit_move_id.payment_id
        payment_debit = partial.debit_move_id.payment_id

        move_credit = partial.credit_move_id.payment_id.reconciled_invoice_ids
        move_debit = partial.debit_move_id.payment_id.reconciled_invoice_ids

        reverse_move_credit = partial.credit_move_id.payment_id.reconciled_bill_ids
        reverse_move_debit = partial.debit_move_id.payment_id.reconciled_bill_ids

        for move in move_credit:
            if (
                payment_credit.is_igtf
                and payment_credit.is_igtf_on_foreign_exchange
                and move
                and move.bi_igtf > 0
            ):
                amount = partial.credit_move_id.payment_id.amount
                if self.env.company.currency_id.id == self.env.ref("base.VEF").id:
                    amount = amount * move.foreign_rate
                result = move.bi_igtf - amount
                if self.env.company.currency_id.id == self.env.ref("base.VEF").id:
                    result = move.bi_igtf - (amount * self.foreign_rate)
                if result < 0:
                    result = 0
                move.write({"bi_igtf": result})

                if payment_credit.is_two_percentage:
                    move.write({"is_two_percentage": True})

        for move in move_debit:
            if (
                payment_debit.is_igtf
                and payment_debit.is_igtf_on_foreign_exchange
                and move
                and move.bi_igtf > 0
            ):
                amount = partial.debit_move_id.payment_id.amount
                if self.env.company.currency_id.id == self.env.ref("base.VEF").id:
                    amount = amount * move.foreign_rate
                result = move.bi_igtf - amount
                if self.env.company.currency_id.id == self.env.ref("base.VEF").id:
                    result = move.bi_igtf - (amount * self.foreign_rate)
                if result < 0:
                    result = 0
                move.write({"bi_igtf": result})
                if payment_debit.is_two_percentage:
                    move.write({"is_two_percentage": True})

        for reverse_credit in reverse_move_credit:
            if (
                payment_credit.is_igtf
                and payment_credit.is_igtf_on_foreign_exchange
                and reverse_credit
                and reverse_credit.bi_igtf > 0
            ):
                amount = partial.credit_move_id.payment_id.amount
                if self.env.company.currency_id.id == self.env.ref("base.VEF").id:
                    amount = amount * reverse_credit.foreign_rate
                result = reverse_credit.bi_igtf - amount
                if self.env.company.currency_id.id == self.env.ref("base.VEF").id:
                    result = reverse_credit.bi_igtf - (amount * self.foreign_rate)
                if result < 0:
                    result = 0
                reverse_credit.write({"bi_igtf": result})
                if payment_credit.is_two_percentage:
                    move_credit.write({"is_two_percentage": True})

        for reverse_debit in reverse_move_debit:
            if (
                payment_debit.is_igtf
                and payment_debit.is_igtf_on_foreign_exchange
                and reverse_debit
                and reverse_debit.bi_igtf > 0
            ):
                amount = partial.debit_move_id.payment_id.amount
                if self.env.company.currency_id.id == self.env.ref("base.VEF").id:
                    amount = amount * reverse_debit.foreign_rate
                result = reverse_debit.bi_igtf - amount
                if self.env.company.currency_id.id == self.env.ref("base.VEF").id:
                    result = reverse_debit.bi_igtf - (amount * self.foreign_rate)
                if result < 0:
                    result = 0
                reverse_debit.write({"bi_igtf": result})
                if payment_debit.is_two_percentage:
                    reverse_debit.write({"is_two_percentage": True})

    def js_remove_outstanding_partial(self, partial_id):
        for move in self:
            move.remove_igtf_from_move(partial_id)
        res = super().js_remove_outstanding_partial(partial_id)
        return res

    def js_assign_outstanding_line(self, line_id):
        amount_residual = self.amount_residual
        res = super().js_assign_outstanding_line(line_id)
        self.recalculate_bi_igtf(
            line_id,
            initial_residual=amount_residual
            if not self.currency_id.is_zero(amount_residual)
            else self.amount_residual,
        )
        return res
