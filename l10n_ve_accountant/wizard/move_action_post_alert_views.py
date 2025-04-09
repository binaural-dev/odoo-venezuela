from odoo import models, fields

class MoveActionPostAlertWizard(models.TransientModel):
    _name = 'move.action.post.alert.wizard'
    _description = 'Move Action Post Alert'

    move_id = fields.Many2one('account.move')
    
    def action_confirm(self):
        self.move_id.with_context(move_action_post_alert=True).action_post()
        return {'type': 'ir.actions.client',
                'tag': 'reload',}

    def action_cancel(self):
        return {'type': 'ir.actions.act_window_close'}

