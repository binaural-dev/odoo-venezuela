from odoo import _, fields, models


class StockPickingType(models.Model):
    _inherit = "stock.picking.type"

    type_steps = fields.Selection(
        [
            ("in", "IN"),
            ("out", "OUT"),
            ("int", "INT"),
            ("pick", "PICK"),
            ("pack", "PACK"),
        ],
        string="Type Steps",
        compute="_compute_type_steps",
        store=True,
    )

    def _compute_type_steps(self):
        for record in self:
            record.type_steps = record._get_type_steps()

    def _get_type_steps(self):
        if self.warehouse_id.in_type_id.id == self.id:
            return "in"
        if self.warehouse_id.out_type_id.id == self.id:
            return "out"
        if self.warehouse_id.int_type_id.id == self.id:
            return "int"
        if self.warehouse_id.pick_type_id.id == self.id:
            return "pick"
        if self.warehouse_id.pack_type_id.id == self.id:
            return "pack"
        return False
