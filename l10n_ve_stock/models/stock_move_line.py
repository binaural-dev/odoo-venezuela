from odoo import _, api, fields, models
from odoo.exceptions import UserError

import logging
_logger = logging.getLogger(__name__)

class StockMoveLine(models.Model):
    _inherit = "stock.move.line"
    _order = "priority_location asc"

    product_tag_ids = fields.Many2many(related="product_id.product_tag_ids")

    priority_location = fields.Integer(
        string="Priority", related="product_id.priority_location", store=True
    )

    def _get_fields_stock_barcode(self):
        res = super()._get_fields_stock_barcode()
        res.append("priority_location")
        return res
