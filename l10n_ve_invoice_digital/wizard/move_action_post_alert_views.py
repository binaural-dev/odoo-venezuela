from odoo import models

class MoveActionPostAlertWizard(models.TransientModel):
    _inherit = 'move.action.post.alert.wizard'

    def action_confirm(self):
        res = super(MoveActionPostAlertWizard, self).action_confirm()

        if self.move_id and self.env.company.invoice_digital_tfhka:
            self.move_id._tfhka_digitalize_on_confirm()

        return res

