# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ReturnPicking(models.TransientModel):
    """
    Inherited for creating return picking from the Direct Shipped Stock moves of Sale order.
    """
    _inherit = "stock.return.picking"

    sale_order_ept_id = fields.Many2one("sale.order")

    @api.onchange('sale_order_ept_id')
    def _onchange_sale_order_id(self):
        """
        When return picking wizard will be opened from Sale order, fields has to be set from the direct moves.
        """
        move_dest_exists = False
        moves = []
        product_return_moves = [(5,)]
        order = self.sale_order_ept_id
        if order and order.moves_count:
            moves = self.env["stock.move"].search(
                [('picking_id', '=', False), ('sale_line_id', 'in', order.order_line.ids)])
            if not moves.filtered(lambda x: x.state == "done"):
                raise UserError(_("You may only return Done moves."))

        line_fields = [f for f in self.env['stock.return.picking.line']._fields.keys()]
        product_return_moves_data_tmpl = self.env['stock.return.picking.line'].default_get(line_fields)
        for move in moves:
            if move.state == 'cancel':
                continue
            if move.scrapped:
                continue
            if move.move_dest_ids:
                move_dest_exists = True
            product_return_moves_data = dict(product_return_moves_data_tmpl)
            product_return_moves_data.update(self._prepare_stock_return_picking_line_vals_from_move(move))
            product_return_moves.append((0, 0, product_return_moves_data))
        if order:
            self.product_return_moves = product_return_moves
            self.move_dest_exists = move_dest_exists
            warehouse = order.warehouse_id
            self.parent_location_id = warehouse and warehouse.view_location_id.id or move.location_id.location_id.id
            self.original_location_id = move.location_id.id
            location_id = move.location_id.id
            if warehouse.out_type_id.return_picking_type_id.default_location_dest_id.return_location:
                location_id = warehouse.out_type_id.return_picking_type_id.default_location_dest_id.id
            self.location_id = location_id
            self.company_id = order.company_id.id

    def create_returns_ept(self):
        """
        Creates return picking for the direct shipped moves.
        @note: Same as base method but with Customisation.
        """
        for wizard in self:
            new_picking_id, pick_type_id = wizard._create_returns_ept()
        # Override the context to disable all the potential filters that could have been set previously
        ctx = dict(self.env.context)
        ctx.update({
            'default_partner_id': self.sale_order_ept_id.partner_shipping_id.id,
            'search_default_picking_type_id': pick_type_id,
            'search_default_draft': False,
            'search_default_assigned': False,
            'search_default_confirmed': False,
            'search_default_ready': False,
            'search_default_planning_issues': False,
            'search_default_available': False,
        })
        return {
            'name': _('Returned Picking'),
            'view_mode': 'form,tree,calendar',
            'res_model': 'stock.picking',
            'res_id': new_picking_id,
            'type': 'ir.actions.act_window',
            'context': ctx,
        }

    def _create_returns_ept(self):
        """
        Creates return picking and return move from the wizard for selected moves.
        @note: Same as base method but with Customisation.
        """
        # TODO sle: the unreserve of the next moves could be less brutal
        if not self.product_return_moves:
            raise UserError(_("Please specify at least one non-zero quantity."))
        for return_move in self.product_return_moves.mapped('move_id'):
            return_move.move_dest_ids.filtered(lambda m: m.state not in ('done', 'cancel'))._do_unreserve()

        # create new picking for returned products
        order = self.sale_order_ept_id
        picking_type_id = order.warehouse_id.out_type_id.return_picking_type_id.id
        new_picking_vals = {
            'move_ids': [],
            'picking_type_id': picking_type_id,
            'state': 'draft',
            'origin': _("Return of %s", order.name),
            'location_id': return_move.location_dest_id.id,
            "sale_id": order.id,
            "partner_id": order.partner_shipping_id.id
        }
        if self.location_id.id:
            new_picking_vals.update({'location_dest_id': self.location_id.id})
        new_picking = self.picking_id.create(new_picking_vals)
        new_picking.message_post_with_view('mail.message_origin_link',
                                           values={'self': new_picking, 'origin': order},
                                           subtype_id=self.env.ref('mail.mt_note').id)
        returned_lines = 0
        group = self.env["procurement.group"].create({"name": order.name, "sale_id": order.id,
                                                      "partner_id": order.partner_id.id})
        for return_line in self.product_return_moves:
            if not return_line.move_id:
                raise UserError(_("You have manually created product lines, please delete them to proceed."))
            # TODO sle: float_is_zero?
            if return_line.quantity:
                returned_lines += 1
                vals = self._prepare_move_default_values(return_line, new_picking)
                vals.update({"warehouse_id": order.warehouse_id.id,
                             "group_id": group.id,
                             "to_refund": return_line.to_refund})
                r = return_line.move_id.copy(vals)
                vals = {}

                # +--------------------------------------------------------------------------------------------------------+
                # |       picking_pick     <--Move Orig--    picking_pack     --Move Dest-->   picking_ship
                # |              | returned_move_ids              ↑                                  | returned_move_ids
                # |              ↓                                | return_line.move_id              ↓
                # |       return pick(Add as dest)          return toLink                    return ship(Add as orig)
                # +--------------------------------------------------------------------------------------------------------+
                move_orig_to_link = return_line.move_id.move_dest_ids.mapped('returned_move_ids')
                # link to original move
                move_orig_to_link |= return_line.move_id
                # link to siblings of original move, if any
                move_orig_to_link |= return_line.move_id \
                    .mapped('move_dest_ids').filtered(lambda m: m.state not in ('cancel')) \
                    .mapped('move_orig_ids').filtered(lambda m: m.state not in ('cancel'))
                move_dest_to_link = return_line.move_id.move_orig_ids.mapped('returned_move_ids')
                # link to children of originally returned moves, if any. Note that the use of
                # 'return_line.move_id.move_orig_ids.returned_move_ids.move_orig_ids.move_dest_ids'
                # instead of 'return_line.move_id.move_orig_ids.move_dest_ids' prevents linking a
                # return directly to the destination moves of its parents. However, the return of
                # the return will be linked to the destination moves.
                move_dest_to_link |= return_line.move_id.move_orig_ids.mapped('returned_move_ids') \
                    .mapped('move_orig_ids').filtered(lambda m: m.state not in ('cancel')) \
                    .mapped('move_dest_ids').filtered(lambda m: m.state not in ('cancel'))
                vals['move_orig_ids'] = [(4, m.id) for m in move_orig_to_link]
                vals['move_dest_ids'] = [(4, m.id) for m in move_dest_to_link]
                r.write(vals)
        if not returned_lines:
            raise UserError(_("Please specify at least one non-zero quantity."))

        new_picking.action_confirm()
        new_picking.action_assign()
        return new_picking.id, picking_type_id
