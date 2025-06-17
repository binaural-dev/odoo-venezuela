from odoo import models

class MoveActionPostAlertWizard(models.TransientModel):
    _inherit = 'move.action.post.alert.wizard'

    def action_confirm(self):
        res = super(MoveActionPostAlertWizard, self).action_confirm()
        if self.move_id:
            self.move_id.generate_document_digital()
        return res

