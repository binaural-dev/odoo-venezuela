from odoo import _, models


class StockPickingType(models.Model):
    _inherit = "stock.picking.type"

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
