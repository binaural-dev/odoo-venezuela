from odoo import _, api, fields, models

class StockMove(models.Model):
    _inherit = "stock.move"
    _order = "priority_location asc"

    priority_location = fields.Integer(
        string="Priority", related="product_id.priority_location", store=True
    )

    def _action_done(self, cancel_backorder=False):
        res = super()._action_done(cancel_backorder=cancel_backorder)
        if self.env.company.use_alternate_locations:
            self._update_alter_location_on_move_done()
        return res

    def _update_alter_location_on_move_done(self):
        alter_location_model = self.env["stock.picking.alter.location"]
        for move in self:
            if not move.product_id.is_storable:
                continue

            warehouse = self._get_warehouse_from_move(move)
            if not warehouse:
                continue

            output_loc = warehouse.wh_output_stock_loc_id
            if not output_loc:
                continue

            alter_location = alter_location_model.search(
                [
                    ("product_id", "=", move.product_id.id),
                    ("warehouse_id", "=", warehouse.id),
                ],
                limit=1,
            )
            if not alter_location:
                continue

            qty = move.quantity
            if qty <= 0:
                continue

            if move.location_dest_id == output_loc:
                alter_location.action_move_to_output(
                    output_loc.id, qty, alter_location.pick_location.id
                )
            elif (
                move.location_id == output_loc
                and move.location_dest_id.usage in ("customer", "supplier")
            ):
                alter_location.action_deliver_from_output(output_loc.id, qty)

    @api.model
    def _get_warehouse_from_move(self, move):
        if move.picking_id and move.picking_id.picking_type_id.warehouse_id:
            return move.picking_id.picking_type_id.warehouse_id
        for loc in (move.location_id, move.location_dest_id):
            wh = self.env["stock.warehouse"].search(
                [("view_location_id", "parent_of", loc.id)], limit=1
            )
            if wh:
                return wh
        return self.env["stock.warehouse"].browse()
