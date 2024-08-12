# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, exceptions, _
from odoo.exceptions import Warning, UserError
from odoo.tools import float_compare
from odoo.tools.float_utils import float_round, float_is_zero


class stockMove(models.Model):
    _inherit = 'stock.move'

    create_exist_lot = fields.Boolean(string="Import Lot/serial with existing lot",
                                      compute="_check_import_lot_serial", store=True)
    create_lot = fields.Boolean(string="Import New Lot/serial",
                                compute="_check_import_lot_serial", store=True)

    @api.depends('picking_id.picking_type_id', 'picking_id.picking_type_id.use_create_lots',
                 'picking_id.picking_type_id.use_existing_lots')
    def _check_import_lot_serial(self):
        for rec in self:
            picking_type = rec.picking_id.picking_type_id
            if picking_type.use_create_lots and picking_type.use_existing_lots:
                rec.update({
                    'create_exist_lot': True,
                    'create_lot': False
                })
            elif picking_type.use_create_lots and not picking_type.use_existing_lots:
                rec.update({
                    'create_exist_lot': False,
                    'create_lot': True
                })
            else:
                rec.update({
                    'create_exist_lot': False,
                    'create_lot': False
                })

    def open_serial_wizard(self):
        view = self.env.ref('import_lot_serial_no.lot_wizard_view')
        ctx = {}
        ctx.update({'default_stock_move_id': self.id})
        return {
            'name': _('Import Lots'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'import.lot.wizard',
            'view_id': view.id,
            'target': 'new',
            'context': ctx
        }

    def _update_reserved_quantity(self, need, available_quantity, location_id, lot_id=None, package_id=None,
                                  owner_id=None, strict=True):
        """ Create or update move lines.
        """

        self.ensure_one()

        lots = []
        for line in self.move_line_ids:
            lots.append(line.lot_id.id)
        if lots:
            lot_id = self.env['stock.lot'].browse(lots)
        else:
            lot_id = self.env['stock.lot']
        if not package_id:
            package_id = self.env['stock.quant.package']
        if not owner_id:
            owner_id = self.env['res.partner']

        taken_quantity = min(available_quantity, need)

        # `taken_quantity` is in the quants unit of measure. There's a possibility that the move's
        # unit of measure won't be respected if we blindly reserve this quantity, a common usecase
        # is if the move's unit of measure's rounding does not allow fractional reservation. We chose
        # to convert `taken_quantity` to the move's unit of measure with a down rounding method and
        # then get it back in the quants unit of measure with an half-up rounding_method. This
        # way, we'll never reserve more than allowed. We do not apply this logic if
        # `available_quantity` is brought by a chained move line. In this case, `_prepare_move_line_vals`
        # will take care of changing the UOM to the UOM of the product.
        if not strict and self.product_id.uom_id != self.product_uom:
            taken_quantity_move_uom = self.product_id.uom_id._compute_quantity(taken_quantity, self.product_uom,
                                                                               rounding_method='DOWN')
            taken_quantity = self.product_uom._compute_quantity(taken_quantity_move_uom, self.product_id.uom_id,
                                                                rounding_method='HALF-UP')

        quants = []
        rounding = self.env['decimal.precision'].precision_get('Product Unit of Measure')

        if self.product_id.tracking == 'serial':
            if float_compare(taken_quantity, int(taken_quantity), precision_digits=rounding) != 0:
                taken_quantity = 0

        try:
            with self.env.cr.savepoint():
                if not float_is_zero(taken_quantity, precision_rounding=self.product_id.uom_id.rounding):
                    quants = self.env['stock.quant']._update_reserved_quantity(
                        self.product_id, location_id, taken_quantity, lot_id=lot_id,
                        package_id=package_id, owner_id=owner_id, strict=strict
                    )
        except UserError:
            taken_quantity = 0

        # Find a candidate move line to update or create a new one.
        for reserved_quant, quantity in quants:
            to_update = self.move_line_ids.filtered(lambda ml: ml._reservation_is_updatable(quantity, reserved_quant))
            if to_update:
                uom_quantity = self.product_id.uom_id._compute_quantity(quantity, to_update[0].product_uom_id,
                                                                        rounding_method='HALF-UP')
                uom_quantity = float_round(uom_quantity, precision_digits=rounding)
                uom_quantity_back_to_product_uom = to_update[0].product_uom_id._compute_quantity(uom_quantity,
                                                                                                 self.product_id.uom_id,
                                                                                                 rounding_method='HALF-UP')
            if to_update and float_compare(quantity, uom_quantity_back_to_product_uom, precision_digits=rounding) == 0:
                to_update[0].with_context(bypass_reservation_update=True).reserved_uom_qty += uom_quantity
            else:
                if self.product_id.tracking == 'serial':
                    for i in range(0, int(quantity)):
                        self.env['stock.move.line'].create(
                            self._prepare_move_line_vals(quantity=1, reserved_quant=reserved_quant))
                else:
                    self.env['stock.move.line'].create(
                        self._prepare_move_line_vals(quantity=quantity, reserved_quant=reserved_quant))
        return taken_quantity