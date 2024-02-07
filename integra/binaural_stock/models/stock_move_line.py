from odoo import _, api, fields, models

class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    product_tag_ids = fields.Many2many(related='product_id.product_tag_ids')