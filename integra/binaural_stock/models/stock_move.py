from odoo import _, api, fields, models

class StockMove(models.Model):
    _inherit = "stock.move"
    _order = "priority_location asc"

    priority_location = fields.Integer(
        string="Priority", related="product_id.priority_location", store=True
    )
