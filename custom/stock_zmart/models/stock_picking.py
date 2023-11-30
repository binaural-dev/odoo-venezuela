import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def print_operation_albaran(self):
        return self.env.ref("stock_zmart.action_print_picking_order").report_action(self)

    shipping_weight = fields.Float(store=True, readonly=False)
    weight = fields.Float(store=True, readonly=False)
    warehouse_operator_id = fields.Many2one("stock.warehouse.operator")
    guide = fields.Char(copy=False)
    origin_sale_id = fields.Many2one("sale.order", compute="_compute_origin_sale_id")

    @api.depends("origin")
    def _compute_origin_sale_id(self):
        for record in self:
            if record.origin:
                sale_id = self.env["sale.order"].sudo().search([("name", "=", record.origin)])
                if not sale_id:
                    record.origin_sale_id = False
                    continue
                record.origin_sale_id = sale_id

    def _check_valid_qty_done_move_line_ids_without_package(self):
        for move_line_id in self.move_line_ids_without_package:

            if move_line_id.qty_done > move_line_id.reserved_uom_qty:
                raise UserError(_("No se pueden validar cantidades superiores a las reservadas."))

            seq_code = move_line_id.picking_id.sequence_code
            is_lower_than = move_line_id.qty_done < move_line_id.reserved_uom_qty
            has_picking_group = self.env.user.has_group ('stock_zmart.group_stock_picking_not_lower_qty_done')

            if seq_code in ['PICK', 'PACK'] and is_lower_than and has_picking_group:
                raise UserError(_("No se pueden validar cantidades inferiores a las reservadas o no tiene el permiso en el grupo de acceso."))

    def button_validate(self):

        # self._check_valid_qty_done_move_line_ids_without_package()

        if not self.guide:
            if self.shipping_type == 'shipment' and self.sequence_code == 'PACK':
                guide_sequence_id = self.env.ref("stock_zmart.sequence_stock_number_guide")

                if not guide_sequence_id:
                    return

                guide_sequence = guide_sequence_id._next()
                self.update({
                    'guide': guide_sequence
                })

        return super().button_validate()


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
