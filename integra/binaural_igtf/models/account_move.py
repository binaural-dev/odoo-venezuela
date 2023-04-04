from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class AccountMoveIgtf(models.Model):
    _inherit = "account.move"

    def default_is_igtf(self):
        return self.env.company.is_igtf or False

    default_is_igtf_config = fields.Boolean(default=default_is_igtf)

    def get_fields(self):
        for move in self:
           _logger.warning("get_fields")
           _logger.warning(move.read())


    def js_remove_outstanding_partial(self, partial_id):
        partial = self.env['account.partial.reconcile'].browse(partial_id)
        
        if partial.credit_move_id.payment_id.reconciled_invoice_ids:
            move = partial.credit_move_id.payment_id.reconciled_invoice_ids
            amount = partial.credit_move_id.payment_id.amount - partial.credit_move_id.payment_id.igtf_amount
            move.write({'bi_igtf': move.bi_igtf - amount})

        if partial.debit_move_id.payment_id.reconciled_invoice_ids:
            move = partial.debit_move_id.payment_id.reconciled_invoice_ids
            amount = partial.debit_move_id.payment_id.amount - partial.debit_move_id.payment_id.igtf_amount
            move.write({'bi_igtf': move.bi_igtf - amount})

        if partial.credit_move_id.payment_id.reconciled_bill_ids:
            move = partial.credit_move_id.payment_id.reconciled_bill_ids
            amount = partial.credit_move_id.payment_id.amount - partial.credit_move_id.payment_id.igtf_amount
            move.write({'bi_igtf': move.bi_igtf - amount})

        if partial.debit_move_id.payment_id.reconciled_bill_ids:
            move = partial.debit_move_id.payment_id.reconciled_bill_ids
            amount = partial.debit_move_id.payment_id.amount - partial.debit_move_id.payment_id.igtf_amount
            move.write({'bi_igtf': move.bi_igtf - amount})
        res = super().js_remove_outstanding_partial(partial_id)

        return res
    