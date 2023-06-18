from odoo import models, fields

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    shipping_type = fields.Selection(
        related = 'sale_id.shipping_type', 
        string = "Shipping type"
    )
    shipping_name_company = fields.Many2one(
        related = 'sale_id.shipping_name_company'
    )
    shipping_method = fields.Selection(
        [
            ("prepaid", "Prepaid"),
            ("free", "Free"),
            ("collect_at_destination", "Collect at Destination"),
        ],
        related = "sale_id.shipping_method",
        default = "free",
        store = True
    )
    packing_factor = fields.Char(
        store = "True"
    )
    sequence_code = fields.Char(
        related = 'picking_type_id.sequence_code'
    )
    guide = fields.Char(
        readonly = False
    )
    
    def print_label(self):
        return self.env.ref('sale_zmart.action_print_label').report_action(self)