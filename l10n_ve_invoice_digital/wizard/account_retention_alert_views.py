from odoo import models, fields

class AccountRetentionAlertWizard(models.TransientModel):
    _name = 'account.retention.alert.wizard'
    _description = 'Account Retention Post Alert'

    move_id = fields.Many2one('account.retention')
    message = fields.Char(readonly=True)
    
    def action_confirm(self):
        self.move_id.tfhka_auto_accept_sequence_mismatch = True
        self.move_id._tfhka_enqueue_digitalization()

    def action_cancel(self):
        return {'type': 'ir.actions.act_window_close'}