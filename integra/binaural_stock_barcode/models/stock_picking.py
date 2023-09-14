from odoo import models


class StockPicking(models.Model):
    _inherit = 'stock.picking.type'


    def _get_barcode_config(self):
        res = super()._get_barcode_config()
        res["restrict_add_exceeding_quantity"] = self.env.company.restrict_add_exceeding_quantity
        return res
