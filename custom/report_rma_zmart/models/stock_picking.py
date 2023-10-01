from odoo import models

class Rma(models.Model):
    _inherit = "stock.picking"

    def button_picking_rma(self):
        return self.env.ref("report_rma_zmart.action_print_picking_rma").report_action(self)