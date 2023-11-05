from odoo import models

class RmaReDeliveryWizard(models.TransientModel):
    _inherit = "rma.delivery.wizard"

    def action_deliver(self):
        res = super().action_deliver()

        rma_ids = self.env.context.get("active_ids")
        rma = self.env["rma"].browse(rma_ids)
        rma.is_action_replace_executed = True
        
        return res