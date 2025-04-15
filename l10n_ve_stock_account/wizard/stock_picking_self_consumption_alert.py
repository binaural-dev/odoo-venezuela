from odoo import models, fields, api

class StockPickingSelfConsumptionWizard(models.TransientModel):
    _name = 'stock.picking.self.consumption.wizard'
    _description = 'Self-Consumption Validation Alert'

    picking_id = fields.Many2one('stock.picking', string="Transfer")
    
    def action_confirm(self):
        self.picking_id.with_context(skip_self_consumption_check=True)._action_done()
        return {'type': 'ir.actions.act_window_close'}

    def action_cancel(self):
        return {'type': 'ir.actions.act_window_close'}

