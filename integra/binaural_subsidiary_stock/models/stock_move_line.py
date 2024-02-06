from odoo import fields, models


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    subsidiary_origin_id = fields.Many2one(
        "account.analytic.account",
        string="Origin Subsidiary",
        related="location_id.warehouse_id.subsidiary_id",
        store=True,
    )

    subsidiary_dest_id = fields.Many2one(
        "account.analytic.account",
        string="Destination Subsidiary",
        related="location_dest_id.warehouse_id.subsidiary_id",
        store=True,
    )
