from odoo import _, api, fields, models


class StockPickingType(models.Model):
    _inherit = "stock.picking.type"

    restrict_add_exceeding_quantity = fields.Boolean(default=True)

    def _get_barcode_config(self):
        res = super()._get_barcode_config()
        res["restrict_add_exceeding_quantity"] = self.restrict_add_exceeding_quantity
        return res
