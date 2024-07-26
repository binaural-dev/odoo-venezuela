from odoo import api, fields, models, _


class StockPicking(models.Model):
    _inherit = "stock.picking"

    distribution_id = fields.Many2one("stock.picking.distribution")
