from odoo import _, api, fields, models
from odoo.exceptions import UserError


class MoveAlterLocationQtitiesWizard(models.TransientModel):
    _name = "move.alter.location.qtities.wizard"
    _description = "Wizard to move physical quantities to other product locations."

    transfer_quantity = fields.Float("Quantities to Transfer")
    allowed_from_location_ids = fields.Many2many(
        "stock.location", compute="_compute_allowed_from_locations"
    )
    allowed_to_location_ids = fields.Many2many(
        "stock.location", compute="_compute_allowed_to_locations"
    )
    from_location = fields.Many2one(
        "stock.location",
        string="From",
        domain="[('id', 'in', allowed_from_location_ids)]",
    )
    to_location = fields.Many2one(
        "stock.location",
        string="To",
        domain="[('id', 'in', allowed_to_location_ids)]",
    )
    stock_alter_location_id = fields.Many2one("stock.picking.alter.location")

    @api.depends("stock_alter_location_id")
    def _compute_allowed_from_locations(self):
        external_location = self.env.ref("stock.stock_location_output")
        for wizard in self:
            if wizard.stock_alter_location_id:
                output_loc = wizard.stock_alter_location_id.warehouse_id.wh_output_stock_loc_id
                wizard.allowed_from_location_ids = (
                    wizard.stock_alter_location_id.stock_alter_location_lines.mapped(
                        "location_id"
                    ).filtered(
                        lambda loc: loc != external_location and loc != output_loc
                    )
                )
            else:
                wizard.allowed_from_location_ids = False

    @api.depends("from_location")
    def _compute_allowed_to_locations(self):
        external_location = self.env.ref("stock.stock_location_output")
        for wizard in self:
            excluded_ids = [external_location.id]
            output_loc = (
                wizard.stock_alter_location_id.warehouse_id.wh_output_stock_loc_id
                if wizard.stock_alter_location_id and wizard.stock_alter_location_id.warehouse_id
                else False
            )
            if output_loc:
                excluded_ids.append(output_loc.id)
            wizard_domain = [
                ("id", "not in", excluded_ids),
                ("usage", "=", "internal"),
            ]
            if wizard.from_location:
                wizard_domain.append(("id", "!=", wizard.from_location.id))
            if wizard.stock_alter_location_id and wizard.stock_alter_location_id.warehouse_id:
                wizard_domain.append(
                    ("id", "child_of", wizard.stock_alter_location_id.warehouse_id.view_location_id.id)
                )
            wizard.allowed_to_location_ids = self.env["stock.location"].search(
                wizard_domain
            )

    @api.onchange("from_location", "to_location")
    def _onchange_exclude_same_location(self):
        if self.from_location and self.to_location == self.from_location:
            self.to_location = False
        if self.to_location and self.from_location == self.to_location:
            self.from_location = False

    def action_transfer_quantities(self):
        self.ensure_one()
        alter = self.stock_alter_location_id

        from_line = alter.stock_alter_location_lines.filtered(
            lambda l: l.location_id.id == self.from_location.id
        )
        if not from_line:
                raise UserError(
                    _("There is no stock in the source location.")
                )
        if self.transfer_quantity > from_line.available_qty:
                raise UserError(
                    _("You cannot transfer more than the available quantity in the location.")
                )

        pick_location = alter.pick_location
        pick_line = alter.stock_alter_location_lines.filtered(
            lambda l: l.location_id == pick_location
        )
        current_pick_qty = pick_line.available_qty if pick_line else 0.0

        if self.to_location == pick_location:
            new_pick_qty = current_pick_qty + self.transfer_quantity
            if alter.max_quantity and new_pick_qty > alter.max_quantity:
                raise UserError(
                    _(
                        "The resulting quantity (%(qty)s) exceeds the maximum "
                        "allowed quantity in the Physical Location (%(maximum)s).",
                        qty=new_pick_qty,
                        maximum=alter.max_quantity,
                    )
                )

        if self.from_location == pick_location:
            new_pick_qty = current_pick_qty - self.transfer_quantity
            if alter.min_quantity and new_pick_qty < alter.min_quantity:
                raise UserError(
                    _(
                        "The resulting quantity (%(qty)s) would fall below the "
                        "minimum required quantity in the Physical Location (%(minimum)s).",
                        qty=new_pick_qty,
                        minimum=alter.min_quantity,
                    )
                )

        alter.action_internal_transfer(
            self.from_location.id,
            self.to_location.id,
            self.transfer_quantity,
        )