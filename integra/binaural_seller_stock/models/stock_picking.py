from odoo import fields, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    seller_id = fields.Many2one("hr.employee", related="sale_id.seller_id", store=True)
