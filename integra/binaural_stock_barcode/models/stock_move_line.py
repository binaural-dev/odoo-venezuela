from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    demanded_qty = fields.Float(compute="_compute_demand_quantities")
    supervisor_approve_to_edit_id = fields.Many2one("hr.employee", readonly=False)

    def set_supervisor_to_edit(self, supervisor_id):
        self.supervisor_approve_to_edit_id = supervisor_id

    @api.constrains("qty_done")
    def _check_qty_done(self):
        for move_line in self:
            if move_line.demanded_qty > 0 and move_line.qty_done > move_line.demanded_qty:
                raise ValidationError(
                    _("The quantity done cannot be greater than the demanded quantity.")
                )

    @api.depends("move_id")
    def _compute_demand_quantities(self):
        for move_line in self:
            product = move_line.product_id
            # Busca los moves del picking, esperando que formen parte de la misma ubicacion, y asgina
            # la suma total de las cantidades en demanda de los 'moves' que se generen durante la operacion.
            picking_moves = move_line.picking_id.move_ids_without_package.filtered(
                lambda move: product.id == move.product_id.id
            )
            move_line.demanded_qty = float(sum([move.product_uom_qty for move in picking_moves]))

    def _get_fields_stock_barcode(self):
        res = super()._get_fields_stock_barcode()
        res.append("demanded_qty")
        return res
