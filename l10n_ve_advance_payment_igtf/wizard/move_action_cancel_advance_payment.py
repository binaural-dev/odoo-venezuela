from odoo import models, fields, _
from odoo.exceptions import UserError

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
        string="Moves to Cancel",
        relation="move_action_cancel_advance_payment_wizard_cross_move_rel",
        column1="wizard_id",
        column2="account_move_id",
    )
    payment_id = fields.Many2one("account.payment", string="Payment")

    partial_id = fields.Many2one("account.partial.reconcile", string="Partial")

    def action_confirm(self):
        for wizard in self:
            for move in wizard.cross_move_ids:
               
                    
                move.line_ids.remove_move_reconcile()
                move.button_draft()
                move.write({'origin_payment_advanced_payment_id': False})
                move.with_context(
                    move_action_cancel_advance_payment=True
                ).button_cancel()

                wizard.payment_id.write({'advanced_move_ids': [(3, move.id)]})

                move.origin_payment_advanced_payment_id = False
                
                    
            partial_id = self.env.context.get("default_partial_id")
            if not partial_id:
                move_lines = wizard.payment_id.move_id.line_ids
                partial_rec = (move_lines.matched_debit_ids | move_lines.matched_credit_ids)[:1]
                if partial_rec:
                    partial_id = partial_rec.id
                
            if partial_id:
                wizard.payment_id.move_id.remove_igtf_from_account_move(partial_id)
                wizard.payment_id.move_id.line_ids.remove_move_reconcile()

        self.flush_recordset() 
    
        return {
            'type': 'ir.actions.client',
            'tag': 'soft_reload',
        }

    def action_cancel(self):
        return {"type": "ir.actions.act_window_close"}


   