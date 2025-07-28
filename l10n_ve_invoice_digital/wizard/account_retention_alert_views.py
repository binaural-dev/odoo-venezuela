from odoo import models, fields, api

class AccountRetentionAlertWizard(models.TransientModel):
    _name = 'account.retention.alert.wizard'
    _description = 'Account Retention Post Alert'

    move_id = fields.Many2one('account.retention')
    message = fields.Char(readonly=True)
    
    def action_confirm(self):
        self.move_id.with_context(account_retention_alert=True).generate_document_digital()

    def action_cancel(self):
        return {'type': 'ir.actions.act_window_close'}