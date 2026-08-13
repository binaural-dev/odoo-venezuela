from odoo import models, fields
from odoo.tools import clean_context

class MoveActionPostAlertWizard(models.TransientModel):
    _name = 'move.action.post.alert.wizard'
    _description = 'Move Action Post Alert'

    move_id = fields.Many2one('account.move')

    def action_confirm(self):
        """Posting this wizard's move must NOT leak this action's own
        ``default_move_id`` (set when account_move.py opened this wizard,
        via context={'default_move_id': move.id}) into the reconciliation
        chain that action_post() can trigger (payment creation, which
        `_inherits` account.move via 'move_id').

        Without clean_context(), any downstream account.payment.create()
        that doesn't explicitly set 'move_id' picks up the leaked
        default_move_id as an implicit default -- causing Odoo's _inherits
        machinery to treat OUR move_id as the payment's pre-existing
        parent record and write the payment's own field values (e.g. its
        journal_id) onto it, instead of creating the payment's own new
        journal entry. If this move was already posted before
        (posted_before=True) that write raises "You cannot edit the
        journal of an account move if it has been posted once." --
        confirmed to be the actual root cause of that recurring error via
        a full production traceback, not a client-side race.
        """
        self.move_id.with_context(
            clean_context(self.env.context), move_action_post_alert=True,
        ).action_post()
        return {'type': 'ir.actions.client',
                'tag': 'reload',}

    def action_cancel(self):
        return {'type': 'ir.actions.act_window_close'}
