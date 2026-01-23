from odoo import models, fields

import logging

_logger = logging.getLogger(__name__)


class MoveActionCancelAdvancePayment(models.TransientModel):
    _name = "move.action.cancel.advance.payment.wizard"
    _description = "Move Action Cancel Advance Payment"

    move_id = fields.Many2one(
        "account.move",
        string="Move",
    )
    cross_move_ids = fields.Many2many(
        "account.move",
        string="Move",
        relation="move_action_cancel_advance_payment_wizard_cross_move_rel",
        column1="wizard_id",
        column2="account_move_id",
    )
    payment_id = fields.Many2one("account.payment", string="Payment")

    partial_id = fields.Many2one("account.partial.reconcile", string="Partial")

    def action_confirm(self):
        """
        Confirms the cancellation of payments and journal entries related to advance payments.

        - If the main journal entry is of type 'entry', it cancels it and clears cross moves.
        - If not 'entry', it removes the associated IGTF using remove_igtf_from_move_advance.
        - Cancels all cross moves that are not already cancelled and removes the advance payment relation.
        - If the related payment is not cancelled, cancels the payment and clears its cross moves and advance relations.

        This method is used from the wizard to unreconcile payments and advance journal entries in Odoo.
        """
        for wizard in self:
            # Cancel cross moves if not already cancelled
            if wizard.move_id.is_entry():
                wizard.move_id.with_context(
                    move_action_cancel_advance_payment=True
                ).button_cancel()
                wizard.move_id.cross_move_ids = [(5, 0, 0)]
            else:
                wizard.move_id.remove_igtf_from_move_advance(wizard.partial_id.id)
            for move in wizard.cross_move_ids:
                if move.state != "cancel":
                    move.with_context(
                        move_action_cancel_advance_payment=True
                    ).button_cancel()
                    move.origin_payment_advanced_payment_id = False
            payment = wizard.payment_id
            if payment and payment.state != "cancel":
                if payment.move_id:
                    payment.move_id.cross_move_ids = [(5, 0, 0)]
                if payment.move_id.state != "cancel":
                    payment.move_id.with_context(
                        move_action_cancel_advance_payment=True
                    ).button_cancel()
                payment.advanced_move_ids = [(5, 0, 0)]
        return {
            "type": "ir.actions.client",
            "tag": "reload",
        }

    def action_cancel(self):
        return {"type": "ir.actions.act_window_close"}
