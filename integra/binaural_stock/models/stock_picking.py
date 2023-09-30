from odoo import api, fields, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    package_qty = fields.Integer(default=0)
    is_out = fields.Boolean(compute="_compute_is_out")

    def _compute_is_out(self):
        for record in self:
            record.is_out = (
                record.picking_type_id.warehouse_id.out_type_id.id == record.picking_type_id.id
            )
