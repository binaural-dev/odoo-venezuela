from odoo import _, api, fields, models
from odoo.exceptions import UserError

import logging
_logger = logging.getLogger(__name__)

class StockMoveLine(models.Model):
    _inherit = "stock.move.line"
    _order = "priority_location asc"

    product_tag_ids = fields.Many2many(related='product_id.product_tag_ids')

    priority_location = fields.Integer(
        string="Priority", related="product_id.priority_location", store=True
    )

    def _get_fields_stock_barcode(self):
        res = super()._get_fields_stock_barcode()
        res.append("priority_location")
        return res
    
    @api.onchange('product_id')
    def _onchange_product_id(self):
        block_transfer_expedition = self.env.user.has_group("l10n_ve_stock.group_block_type_inventory_transfers_expeditions")

        if block_transfer_expedition:
            
            id_str = str(self.picking_id.id)
            
            if "_" in id_str:
                id_numero = id_str.split("_")[1]
            else:
                id_numero = id_str

            stock_picking = self.env["stock.picking"].sudo().search([("id", "=", id_numero)])

            if stock_picking.picking_type_id and stock_picking.picking_type_id.code == "outgoing":
                raise UserError(_("You do not have permission to add lines to this transfer."))