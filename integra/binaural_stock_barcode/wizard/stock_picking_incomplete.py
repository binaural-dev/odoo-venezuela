from odoo.exceptions import UserError, ValidationError
from odoo.models import TransientModel
from odoo import api, fields, models, _


class StockBackorderConfirmation(models.TransientModel):
    _name = "stock.picking.incomplete"
    _description = "Operation outgoing wizard validation."

    pick_id = fields.Many2one("stock.picking")
    move_ids = fields.Many2many("stock.move", compute="_compute_move_ids_incomplete")

    @api.depends("pick_id")
    def _compute_move_ids_incomplete(self):
        for record in self:
            record.move_ids = False
            for move in record.pick_id.move_ids:
                if move.product_uom_qty - move.quantity_done != 0:
                    record.move_ids |= move

    def process(self):
        pickings_to_validate_ids = self.env.context.get("button_validate_picking_ids")
        if pickings_to_validate_ids:
            pickings_to_validate = self.env["stock.picking"].browse(pickings_to_validate_ids)
            return pickings_to_validate.with_context(
                skip_incomplete_qty=True
            ).button_validate()
        return True
