import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_is_zero

_logger = logging.getLogger(__name__)


class StockPickingAlterLocation(models.Model):
    _name = "stock.picking.alter.location"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Alternate Locations"

    active = fields.Boolean(default=True, tracking=True)

    pick_quantity = fields.Float(
        "Physical Quantities",
        compute="_compute_pick_quantity",
    )
    total_alter_quantity = fields.Float(
        "Total in Alter Locations",
        compute="_compute_total_alter_quantity",
    )
    total_quantity = fields.Float(
        "Quantity in Other Locations", compute="_compute_total_quantity_in_locations"
    )
    min_quantity = fields.Float("Minimum Quantity", tracking=True)
    max_quantity = fields.Float("Maximum Quantity", tracking=True)

    name = fields.Char("Product Name", related="product_id.name", tracking=True)
    product_id = fields.Many2one("product.product", string="Product")
    pick_location = fields.Many2one(
        "stock.location",
        string="Physical Location",
        tracking=True,
    )
    warehouse_id = fields.Many2one(
        "stock.warehouse",
        string="Warehouse",
        compute="_compute_warehouse_id",
        store=True,
        tracking=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        compute="_compute_company_id",
        store=True,
    )
    stock_alter_location_lines = fields.One2many(
        "stock.picking.alter.location.line",
        "stock_alter_location_id",
        string="Other Product Locations",
    )

    @api.depends("pick_location")
    def _compute_warehouse_id(self):
        warehouse_model = self.env["stock.warehouse"]
        for rec in self:
            rec.warehouse_id = False
            if not rec.pick_location:
                continue
            loc = rec.pick_location
            while loc:
                wh = warehouse_model.search(
                    [("view_location_id", "=", loc.id)], limit=1
                )
                if wh:
                    rec.warehouse_id = wh.id
                    break
                loc = loc.location_id

    @api.depends("warehouse_id")
    def _compute_company_id(self):
        for rec in self:
            rec.company_id = rec.warehouse_id.company_id.id or self.env.company.id

    def action_change_product_quantities(self):
        view = self.env.ref(
            "l10n_ve_stock.move_alter_location_qtities_wizard_view_form"
        )
        list_of_locations = [
            line.location_id.id for line in self.stock_alter_location_lines
        ]
        if self.pick_location:
            _logger.info(f'SELF PICK LOCATION:{self.pick_location}')
            list_of_locations.append(self.pick_location.id)

        _logger.info(f'LISTS OF LOCATIONS:{list_of_locations}')

        return {
            "name": _("Change Quantities Between Locations"),
            "type": "ir.actions.act_window",
            "view_mode": "form",
            "res_model": "move.alter.location.qtities.wizard",
            "views": [(view.id, "form")],
            "view_id": view.id,
            "target": "new",
            "context": dict(
                default_to_location=self.pick_location.id,
                default_stock_alter_location_id=self.id,
                min=self.min_quantity,
                domain_locations=list_of_locations,
            ),
        }

    @api.depends("stock_alter_location_lines.available_qty",
                  "stock_alter_location_lines.location_id")
    def _compute_total_alter_quantity(self):
        for rec in self:
            total = 0.0
            output_loc = (
                rec.warehouse_id.wh_output_stock_loc_id
                if rec.warehouse_id
                else False
            )
            for line in rec.stock_alter_location_lines:
                if output_loc and line.location_id == output_loc:
                    continue
                total += line.available_qty
            rec.total_alter_quantity = total

    @api.depends("stock_alter_location_lines.available_qty",
                  "stock_alter_location_lines.location_id",
                  "pick_location")
    def _compute_pick_quantity(self):
        for rec in self:
            pick_line = rec.stock_alter_location_lines.filtered(
                lambda l: l.location_id == rec.pick_location
            )
            rec.pick_quantity = sum(pick_line.mapped("available_qty"))

    @api.depends(
        "stock_alter_location_lines.available_qty",
        "stock_alter_location_lines.location_id",
        "pick_location",
        "warehouse_id.wh_output_stock_loc_id",
    )
    def _compute_total_quantity_in_locations(self):
        for rec in self:
            pick_loc = rec.pick_location
            output_loc = (
                rec.warehouse_id.wh_output_stock_loc_id
                if rec.warehouse_id
                else False
            )
            total = 0.0
            for line in rec.stock_alter_location_lines:
                if pick_loc and line.location_id == pick_loc:
                    continue
                if output_loc and line.location_id == output_loc:
                    continue
                else:
                    total += line.available_qty
            rec.total_quantity = total

    def check_location_in_lines(self, location_id):
        self.ensure_one()
        return location_id.id in self.stock_alter_location_lines.mapped("location_id").ids

    def get_line(self, location_id):
        alt_lines = self.stock_alter_location_lines
        alt_line = alt_lines.filtered(
            lambda line: location_id.id == line.location_id.id
        )
        return alt_line

    def action_internal_transfer(self, from_location_id, to_location_id, transfer_quantity):
        self.ensure_one()
        user = self.env.user
        alter_env = self.with_env(self.env(user=user.id, su=True))

        from_line = alter_env.stock_alter_location_lines.filtered(
            lambda l: l.location_id.id == from_location_id
        )
        to_line = alter_env.stock_alter_location_lines.filtered(
            lambda l: l.location_id.id == to_location_id
        )
        pick_location = alter_env.pick_location

        if not from_line:
            raise UserError(_("There is no stock in the source location."))
        if transfer_quantity > from_line.available_qty:
            raise UserError(
                _("You cannot transfer more than the available quantity in the location.")
            )

        if to_location_id == pick_location.id:
            pick_line = alter_env.stock_alter_location_lines.filtered(
                lambda l: l.location_id == pick_location
            )
            current_pick_qty = pick_line.available_qty if pick_line else 0.0
            new_pick_qty = current_pick_qty + transfer_quantity
            if self.max_quantity and new_pick_qty > self.max_quantity:
                raise UserError(
                    _(
                        "The resulting quantity (%(qty)s) exceeds the maximum "
                        "allowed quantity in the Physical Location (%(maximum)s).",
                        qty=new_pick_qty,
                        maximum=self.max_quantity,
                    )
                )

        if from_location_id == pick_location.id:
            pick_line = alter_env.stock_alter_location_lines.filtered(
                lambda l: l.location_id == pick_location
            )
            current_pick_qty = pick_line.available_qty if pick_line else 0.0
            new_pick_qty = current_pick_qty - transfer_quantity
            if self.min_quantity and new_pick_qty < self.min_quantity:
                raise UserError(
                    _(
                        "The resulting quantity (%(qty)s) would fall below the "
                        "minimum required quantity in the Physical Location (%(minimum)s).",
                        qty=new_pick_qty,
                        minimum=self.min_quantity,
                    )
                )

        from_line.available_qty -= transfer_quantity
        if float_is_zero(from_line.available_qty, precision_rounding=0.01):
            from_line.unlink()
        if to_line:
            to_line.available_qty += transfer_quantity
            if float_is_zero(to_line.available_qty, precision_rounding=0.01):
                to_line.unlink()
        else:
            alter_env.write(
                {
                    "stock_alter_location_lines": [
                        (
                            0,
                            0,
                            {
                                "location_id": to_location_id,
                                "available_qty": transfer_quantity,
                            },
                        )
                    ]
                }
            )

    def action_receive_quantity(self, location_id, qty):
        self.ensure_one()
        user = self.env.user
        alter_env = self.with_env(self.env(user=user.id, su=True))
        alter_line = alter_env.stock_alter_location_lines.filtered(
            lambda l: l.location_id.id == location_id
        )
        if alter_line:
            alter_line.available_qty += qty
            if float_is_zero(alter_line.available_qty, precision_rounding=0.01):
                alter_line.unlink()
        else:
            self.env["stock.picking.alter.location.line"].sudo().create(
                {
                    "stock_alter_location_id": self.id,
                    "location_id": location_id,
                    "available_qty": qty,
                }
            )

    def action_move_to_output(self, output_loc_id, qty, source_loc_id):
        self.ensure_one()
        user = self.env.user
        alter_env = self.with_env(self.env(user=user.id, su=True))
        output_line = alter_env.stock_alter_location_lines.filtered(
            lambda l: l.location_id.id == output_loc_id
        )
        if output_line:
            output_line.available_qty += qty
            if float_is_zero(output_line.available_qty, precision_rounding=0.01):
                output_line.unlink()
        else:
            self.env["stock.picking.alter.location.line"].sudo().create(
                {
                    "stock_alter_location_id": self.id,
                    "location_id": output_loc_id,
                    "available_qty": qty,
                }
            )
        source_line = alter_env.stock_alter_location_lines.filtered(
            lambda l: l.location_id.id == source_loc_id
        )
        if source_line:
            source_line.available_qty -= qty
            if float_is_zero(source_line.available_qty, precision_rounding=0.01):
                source_line.unlink()
        else:
            self.env["stock.picking.alter.location.line"].sudo().create(
                {
                    "stock_alter_location_id": self.id,
                    "location_id": source_loc_id,
                    "available_qty": -qty,
                }
            )

    def action_deliver_from_output(self, output_loc_id, qty):
        self.ensure_one()
        user = self.env.user
        alter_env = self.with_env(self.env(user=user.id, su=True))
        output_line = alter_env.stock_alter_location_lines.filtered(
            lambda l: l.location_id.id == output_loc_id
        )
        if output_line:
            output_line.available_qty -= qty
            if float_is_zero(output_line.available_qty, precision_rounding=0.01):
                output_line.unlink()

    def subtract_physical_quantity(self):
        if not self.env.company.use_alternate_locations:
            return
        quant_model = self.env["stock.quant"]

        for pl in self:
            user = self.env.user
            pl_env = pl.with_env(self.env(user=user.id, su=True))
            _logger.info("Starting adjustment of %s", pl_env.product_id.display_name)
            warehouse = pl_env.warehouse_id
            if not warehouse:
                _logger.warning(
                    "Warehouse not found for %s, skipping", pl_env.display_name
                )
                continue

            output_loc = warehouse.wh_output_stock_loc_id
            internal_locations = warehouse.view_location_id.child_internal_location_ids
            if output_loc:
                internal_locations -= output_loc

            quants = quant_model.search(
                [
                    ("product_id", "=", pl_env.product_id.id),
                    ("location_id", "in", internal_locations.ids),
                ]
            )
            quant_total = sum(quants.mapped("quantity"))

            physical_total = pl_env.total_alter_quantity

            _logger.info(
                "[%s] Total physical quantity: %s, Quant quantity: %s",
                pl_env.display_name,
                physical_total,
                quant_total,
            )

            diff = physical_total - quant_total
            if diff != 0:
                pick_line = pl_env.stock_alter_location_lines.filtered(
                    lambda l: l.location_id == pl_env.pick_location
                )
                if pick_line:
                    pick_line.available_qty -= diff
                    if float_is_zero(pick_line.available_qty, precision_rounding=0.01):
                        pick_line.unlink()
                else:
                    self.env(user=user.id, su=True)["stock.picking.alter.location.line"].create(
                        {
                            "stock_alter_location_id": pl_env.id,
                            "location_id": pl_env.pick_location.id,
                            "available_qty": -diff,
                        }
                    )
                _logger.info(
                    "[%s] pick_quantity adjusted from %s to %s",
                    pl_env.product_id.display_name,
                    physical_total,
                    pl_env.pick_quantity,
                )

            if output_loc:
                output_quant = quant_model.search(
                    [
                        ("product_id", "=", pl_env.product_id.id),
                        ("location_id", "=", output_loc.id),
                    ],
                    limit=1,
                )
                output_line = pl_env.stock_alter_location_lines.filtered(
                    lambda l: l.location_id == output_loc
                )
                if output_quant:
                    output_total = output_quant.quantity
                    if output_line:
                        output_line.available_qty = output_total
                        if float_is_zero(output_line.available_qty, precision_rounding=0.01):
                            output_line.unlink()
                    else:
                        self.env(user=user.id, su=True)["stock.picking.alter.location.line"].create(
                            {
                                "stock_alter_location_id": pl_env.id,
                                "location_id": output_loc.id,
                                "available_qty": output_total,
                            }
                        )
                elif output_line:
                    output_line.unlink()