from odoo import fields, models, _


class StockPickingDistribution(models.Model):
    _inherit = "stock.picking.distribution"

    seller_id = fields.Many2one("hr.employee", domain=[("is_seller", "=", True)])
    picking_seller_ids = fields.One2many(related="picking_ids", readonly=False)

    
