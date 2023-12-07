from odoo import api, fields, models, _
from odoo.exceptions import UserError

import logging

_logger = logging.getLogger(__name__)

from odoo.exceptions import ValidationError

class StockPicking(models.Model):
    _inherit = "stock.picking"

    package_qty = fields.Integer(default=0)
    is_out = fields.Boolean(compute="_compute_is_out")

    change_weight = fields.Boolean(
        related='company_id.change_weight',
    )
    def _compute_is_out(self):
        for record in self:
            record.is_out = (
                record.picking_type_id.warehouse_id.out_type_id.id == record.picking_type_id.id
            )

    @api.model_create_multi
    def create(self, vals_list):
        for val in vals_list:
            self.validate_block_transfers_expedition(vals=val)
        return super().create(vals_list)
    
    def write(self,vals):
        res = super().write(vals)
        keys_to_check = [
            "move_line_ids_without_package",
            "move_line_nosuggest_ids",
            "move_ids_without_package"
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
            "binaural_stock.group_block_type_inventory_transfers_expeditions"
        )
        if block_transfer_expedition:
            picking_type = (
                self.env["stock.picking.type"].search([("id", "=", vals.get("picking_type_id", False))])
                if vals
                else self.picking_type_id
            )
            if picking_type.code == "outgoing":
                if write and matched_key:
                    for move_line in write[matched_key]:
                        if isinstance(move_line[1], str):
                            raise UserError(_("You cannot add products to shipment-type transfers"))
                    
                        if isinstance(move_line[1], int):
                            if move_line[2]["quantity_done"]:
                                lines = self[matched_key]
                                for line in lines:
                                    if line.id == move_line[1]:
                                        if line.product_uom_qty < move_line[2]["quantity_done"]:
                                            raise UserError(_("You cannot make transfers larger than the demand"))
                            
                else: raise UserError(_("You do not have permission to make shipment-type transfers"))
