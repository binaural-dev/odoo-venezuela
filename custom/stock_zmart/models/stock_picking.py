from odoo import models, fields,api

class StockPicking(models.Model):
    _inherit = 'stock.picking'
    
    def print_operation_albaran(self):
        return self.env.ref('stock_zmart.action_print_picking_order').report_action(self)

    shipping_weight = fields.Float(store=True, readonly=False)
    weight = fields.Float(store=True, readonly=False)
