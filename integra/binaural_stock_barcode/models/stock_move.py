from odoo import _, api, fields, models


class StockMoveLine(models.Model):
    _inherit = "stock.move"

    def _get_fields_stock_barcode(self):
        return ["product_id","product_uom_qty","location_id", "product_uom"]

