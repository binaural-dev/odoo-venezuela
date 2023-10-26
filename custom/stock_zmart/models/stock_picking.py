from odoo import models, fields, api


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def print_operation_albaran(self):
        return self.env.ref("stock_zmart.action_print_picking_order").report_action(self)

    shipping_weight = fields.Float(store=True, readonly=False)
    weight = fields.Float(store=True, readonly=False)

    def write(self, vals):
        res = super().write(vals)
        if vals.get("shipping_weight", False):
            picking_ids = self.env["stock.picking"].search(
                [
                    "&",
                    ("origin", "=", self[0].origin),
                    ("shipping_weight", "!=", vals.get("shipping_weight")),
                ],
                limit=1,
            )
            if picking_ids:
                picking_ids.write({"shipping_weight": vals.get("shipping_weight", False)})

        if vals.get("weight", False):
            picking_ids = self.env["stock.picking"].search(
                [
                    "&",
                    ("origin", "=", self.origin),
                    ("weight", "!=", vals.get("weight")),
                ],
                limit=1,
            )
            if picking_ids:
                picking_ids.write({"weight": vals.get("weight", False)})
        return res
