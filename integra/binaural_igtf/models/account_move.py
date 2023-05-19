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

        if (
            payment_credit.is_igtf
            and payment_credit.is_igtf_on_foreign_exchange
            and move_credit
            and move_credit.bi_igtf > 0
        ):
            amount = partial.credit_move_id.payment_id.amount
            result = move_credit.bi_igtf - amount
            if result < 0:
                result = 0
            move_credit.write({"bi_igtf": result})

        if (
            payment_debit.is_igtf
            and payment_debit.is_igtf_on_foreign_exchange
            and move_debit
            and move_debit.bi_igtf > 0
        ):
            amount = partial.debit_move_id.payment_id.amount
            result = move_debit.bi_igtf - amount
            if result < 0:
                result = 0
            move_debit.write({"bi_igtf": result})

        if (
            payment_credit.is_igtf
            and payment_credit.is_igtf_on_foreign_exchange
            and reverse_move_credit
            and reverse_move_credit.bi_igtf > 0
        ):
            amount = partial.credit_move_id.payment_id.amount
            result = reverse_move_credit.bi_igtf - amount
            if result < 0:
                result = 0
            reverse_move_credit.write({"bi_igtf": result})

        if (
            payment_debit.is_igtf
            and payment_debit.is_igtf_on_foreign_exchange
            and reverse_move_debit
            and reverse_move_debit.bi_igtf > 0
        ):
            amount = partial.debit_move_id.payment_id.amount
            result = reverse_move_debit.bi_igtf - amount
            if result < 0:
                result = 0
            reverse_move_debit.write({"bi_igtf": result})

    def js_remove_outstanding_partial(self, partial_id):
        self.remove_igtf_from_move(partial_id)
        res = super().js_remove_outstanding_partial(partial_id)
        return res
