import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.fields import Domain
_logger = logging.getLogger(__name__)



class StockPicking(models.Model):
    _inherit = "stock.picking"

    package_qty = fields.Integer(default=0)
    reception_date = fields.Date(tracking=True)

    def _get_action_picking_delivery_type(self, picking_type):
        # action = self.env["ir.actions.actions"]._for_xml_id("stock.action_picking_tree_all")
        pickings = self.env["stock.picking"]
        if self.reference_ids:
            pickings = self.search(
                [
                    "&",
                    ("reference_ids", "=", self.reference_ids.id),
                    ("type_delivery_step", "=", picking_type),
                ]
            )
            pickings -= self
        action = self.env["ir.actions.actions"]._for_xml_id("stock.action_picking_tree_all")

        if len(pickings) > 1:
            action["domain"] = [("id", "in", pickings.ids)]
        elif pickings:
            form_view = [(self.env.ref("stock.view_picking_form").id, "form")]
            if "views" in action:
                action["views"] = form_view + [
                    (state, view) for state, view in action["views"] if view != "form"
                ]
            else:
                action["views"] = form_view
            action["res_id"] = pickings.id
        # Prepare the context.
        picking_id = pickings.filtered(lambda l: l.picking_type_id.code == "outgoing")
        if picking_id:
            picking_id = picking_id[0]
        else:
            if not pickings:
                raise UserError(_("does not have results from other pickings"))
            picking_id = pickings[0]
        action["context"] = dict(
            self._context,
            default_partner_id=self.partner_id.id,
            default_picking_type_id=picking_id.picking_type_id.id,
            default_origin=self.name,
            default_reference_ids=picking_id.reference_ids.id,
            default_type_delivery_step=picking_type,
        )
        return action

    def action_get_picks(self):
        return self._get_action_picking_delivery_type("pick")

    def action_get_packs(self):
        return self._get_action_picking_delivery_type("pack")

    def action_get_outs(self):
        return self._get_action_picking_delivery_type("out")

    picks_count = fields.Integer(compute="_compute_stock_pickings_by_origin")
    packs_count = fields.Integer(compute="_compute_stock_pickings_by_origin")
    outs_count = fields.Integer(compute="_compute_stock_pickings_by_origin")

    ##TODO Considerar si se pueden refactorizar estas funciones y dejar una sola a la que se le pase
    ###### el tipo de picking.
    def _get_picks(self, assigned=False):
        if not self.reference_ids:
            return self.env["stock.picking"]
        domain = [
            "&",
            ("reference_ids", "in", self.reference_ids.ids),
            ("type_delivery_step", "=", "pick"),
            ("id", "!=", self.id),
        ]
        if assigned:
            if self.type_delivery_step == "pick":
                return self

            domain = Domain.AND([[("state", "in", ["assigned", "waiting"])], domain])
            return self.search(domain, limit=1)
        return self.search(domain)

    def _get_packs(self, assigned=False):
        if not self.reference_ids:
            return self.env["stock.picking"]
        domain = [
            "&",
            ("reference_ids", "in", self.reference_ids.ids),
            ("type_delivery_step", "=", "pack"),
            ("id", "!=", self.id),
        ]
        if assigned:
            if self.type_delivery_step == "pack":
                return self

            domain = Domain.AND([[("state", "in", ["assigned", "waiting"])], domain])
            return self.search(domain, limit=1)
        return self.search(domain)

    def _get_outs(self, assigned=False):
        if not self.reference_ids:
            return self.env["stock.picking"]
        domain = [
            "&",
            ("reference_ids", "in", self.reference_ids.ids),
            ("type_delivery_step", "=", "out"),
            ("id", "!=", self.id),
        ]
        if assigned:
            if self.type_delivery_step == "out":
                return self

            domain = Domain.AND([[("state", "in", ["assigned", "waiting"])], domain])
            return self.search(domain, limit=1)
        return self.search(domain)

    ##END TODO

    @api.depends("picks_count", "packs_count", "outs_count")
    def _compute_stock_pickings_by_origin(self):
        for record in self:
            record.picks_count = len(record._get_picks())
            record.packs_count = len(record._get_packs())
            record.outs_count = len(record._get_outs())

    type_delivery_step = fields.Selection(
        [
            ("in", "IN"),
            ("out", "OUT"),
            ("int", "INT"),
            ("pack", "PACK"),
            ("pick", "PICK"),
        ],
        compute="_compute_type_delivery_step",
        store=True,
    )

    @api.depends("picking_type_id")
    def _compute_type_delivery_step(self):
        for record in self:
            record.type_delivery_step = record.picking_type_id._get_type_steps()

    change_weight = fields.Boolean(
        related="company_id.change_weight",
    )

    # def _compute_is_out(self):
    #     for record in self:
    #         record.is_out = (
    #             record.picking_type_id.warehouse_id.out_type_id.id == record.picking_type_id.id
    #         )

    @api.model_create_multi
    def create(self, vals_list):
        for val in vals_list:
            self.validate_block_transfers_expedition(vals=val)
        res = super().create(vals_list)
        
        self.move_line_ids.sorted(key=lambda x: x.priority_location)
        return res

    def write(self, vals):
        res = super().write(vals)
        
        self.move_line_ids.sorted(key=lambda x: x.priority_location)
        keys_to_check = [
            "move_line_nosuggest_ids",
            "move_ids_without_package",
        ]
        matched_key = None
        for key in keys_to_check:
            if key in vals:
                matched_key = key
                break

        if matched_key:
            self.validate_block_transfers_expedition(write=vals, matched_key=matched_key)

        return res

    def validate_block_transfers_expedition(self, vals=None, write=None, matched_key=None):
        block_transfer_expedition = self.env.user.has_group(
            "l10n_ve_stock.group_block_type_inventory_transfers_expeditions"
        )
        if block_transfer_expedition:
            picking_type = (
                self.env["stock.picking.type"].search(
                    [("id", "=", vals.get("picking_type_id", False))]
                )
                if vals
                else self.picking_type_id
            )
            if picking_type.code == "outgoing":
                if write and matched_key:
                    for move_line in write[matched_key]:
                        if isinstance(move_line[1], str):
                            raise UserError(_("You cannot add products to shipment-type transfers"))

                        if isinstance(move_line[1], int):
                            if not move_line[2]:
                                raise UserError(
                                    _("You cannot add products to shipment-type transfers")
                                )

                            if "quantity" in move_line[2] or "quantity" in move_line[2]:
                                lines = self[matched_key]
                                for line in lines:
                                    if line.id == move_line[1]:
                                        if "quantity" in move_line[2]:
                                            quantity_done = move_line[2].get("quantity")
                                            if line.product_uom_qty < quantity_done:
                                                raise UserError(
                                                    _(
                                                        "You cannot make transfers larger than the demand"
                                                    )
                                                )
                                        elif "quantity" in move_line[2]:
                                            quantity_done = move_line[2].get("quantity")
                                            # if line.quantity_product_uom < quantity_done: ??
                                            if line.reserved_uom_qty < quantity_done:
                                                raise UserError(
                                                    _(
                                                        "You cannot make transfers larger than the reserved quantity"
                                                    )
                                                )

                else:
                    raise UserError(_("You do not have permission to make shipment-type transfers"))

    def action_assign(self):
        for picking in self:
            if picking.type_delivery_step != "pick":
                picking = picking.with_context(skip_physical_location=True)
        return super().action_assign()

    def button_validate(self):
        if self.env.company.not_allow_negative_stock_movement:
            res = super(StockPicking, self).button_validate()
            if isinstance(res, dict) and res.get('res_model') == 'stock.backorder.confirmation':
                return res
            else:
                self._check_stock_availability_for_pickings()
        return super().button_validate()
        
    def _check_stock_availability_for_pickings(self):
        if self.picking_type_id.code in ['internal', 'outgoing']:
            group_product_location_lot = {}
            
            all_move_lines_to_check = self.env['stock.move.line']
            for picking in self:
                all_move_lines_to_check |= picking.move_line_ids

            for line in all_move_lines_to_check:
                if line.product_id.type == 'consu':
                    qty_done_line = line.quantity 
                    if qty_done_line <= 0:
                        continue 

                    key = (line.product_id.id, line.lot_id.id if line.lot_id else False, line.location_id.id)
                    
                    group_product_location_lot[key] = \
                        group_product_location_lot.get(key, 0.0) + qty_done_line

            stock_msg = []

            for key, total_qty_to_move in group_product_location_lot.items():
                product_id, lot_id, location_id = key
                
                product_obj = self.env['product.product'].browse(product_id)
                location_obj = self.env['stock.location'].browse(location_id)
                lot_obj = self.env['stock.lot'].browse(lot_id) if lot_id else False

                context_to_stock = {'location': location_obj.id}
                if lot_obj:
                    context_to_stock['lot_id'] = lot_obj.id
                
                qty_real_allow = \
                    product_obj.with_context(context_to_stock).qty_available - \
                    total_qty_to_move
                
                if qty_real_allow < 0:
                    info_lote_serial = f" ({_('Lot/Serial')}: {lot_obj.name})" if lot_obj else ""
                    stock_msg.append(
                        _("%s%s", product_obj.display_name, info_lote_serial)
                    )
            
            if stock_msg:
                error_msg = _(
                    "Insufficient stock:\n%s\n\nAdjust quantitys or request stock for this location."
                ) % "\n".join(stock_msg)
                raise ValidationError(error_msg)