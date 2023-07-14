from odoo import models, fields,api
import logging
_logger = logging.getLogger(__name__)

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    package_qty = fields.Integer(
        "Package Quantity", 
        help = "Quantity of packages used in the picking"
    )
    destiny = fields.Char()
    shipping_method  = fields.Many2one(
        related = "sale_id.shipping_method"
    )
    comercial = fields.Many2one(
        related = "sale_id.user_id"
    )
    
    action_report_picking_2_datetime = fields.Datetime(string='Fecha y Hora de Ejecución')

    def action_report_picking_2(self):
        # Establece la fecha y hora de ejecución en el registro actual
        self.write({'action_report_picking_2_datetime': fields.Datetime.now()})

        # Ejecuta la acción original
        return self.env.ref('seguridad_stock.action_report_picking_2').report_action(self)