from odoo import models, fields, api, _

class Rma(models.Model):
    _inherit = "rma"

    is_action_replace_executed = fields.Boolean(string='Action Replace Executed',default=False)

    def button_rma_note(self):
        return self.env.ref("report_rma_zmart.action_rma_note").report_action(self)