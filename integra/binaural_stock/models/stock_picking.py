from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class StockPicking(models.Model):
    _inherit = "stock.picking"

    package_qty = fields.Integer(default=0)
    is_out = fields.Boolean(compute="_compute_is_out")

    change_weight = fields.Boolean(
        related='company_id.change_weight',
    )
    def _compute_is_out(self):
        for record in self:
            record.is_out = (
                record.picking_type_id.warehouse_id.out_type_id.id == record.picking_type_id.id
            )
