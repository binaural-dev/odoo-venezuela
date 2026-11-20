from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

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

    def action_scrap(self):
        self._check_scrap_quantity()
        return super().action_scrap()

    def _check_scrap_quantity(self):
        """Block a scrap beyond the stock of its location or beyond what its order manufactured.

        In Odoo 20 a scrap is a stock move (``stock.scrap`` no longer exists) and the core only warns
        when the location does not have enough. The two company settings of Odoo 19 still decide:
        without "allow to scrap more than available" the scrap is refused, and with "do not scrap more
        than manufactured" the done scraps of a production order plus this one cannot exceed what the
        order produced.
        """
        self.ensure_one()
        company = self.env.company
        if not company.allow_scrap_more_than_available and not self.check_available_qty():
            raise ValidationError(_("You cannot scrap more than the available product quantity in this location."))
        if not company.not_allow_scrap_more_than_what_was_manufactured:
            return
        production = self._get_scrap_production()
        if not production:
            return
        scrapped = self._get_production_scrapped_quantity(production)
        produced = production.qty_produced
        if scrapped >= produced or self.quantity + scrapped > produced or self.quantity > produced:
            raise ValidationError(_("No more than what is manufactured can be discarded in this operation."))

    def _get_scrap_production(self):
        """Return the production order of a scrap move, or an empty value without manufacturing."""
        if "production_id" not in self._fields:
            return False
        return self.production_id or self.raw_material_production_id

    def _get_production_scrapped_quantity(self, production):
        """Return the quantity already scrapped, and done, from a production order."""
        moves = self.search([
            ("id", "not in", self.ids),
            ("is_scrap", "=", True),
            ("state", "=", "done"),
            "|",
            ("production_id", "=", production.id),
            ("raw_material_production_id", "=", production.id),
        ])
        return sum(moves.mapped("quantity"))
