from odoo import models, fields


class StockQuantityHistoryInh(models.TransientModel):
    _inherit = "stock.quantity.history"

    def get_fields_products(self):
        res = super().get_fields_products()
        res.append("brand_id")
        return res
