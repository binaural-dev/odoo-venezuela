from odoo import api, fields, models, _
from odoo.exceptions import UserError

import logging

_logger = logging.getLogger(__name__)

class StockPicking(models.Model):
    _inherit = "stock.picking"

    package_qty = fields.Integer(default=0)
    is_out = fields.Boolean(compute="_compute_is_out")

    def _compute_is_out(self):
        for record in self:
            record.is_out = (
                record.picking_type_id.warehouse_id.out_type_id.id == record.picking_type_id.id
            )

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        self.validate_block_transfers_expedition(vals_list)
        return res
    
    def button_validate(self):
        self.validate_block_transfers_expedition()
        return super().button_validate()

    def validate_block_transfers_expedition(self, vals=None):
        block_transfer_expedition = self.env.user.has_group("binaural_stock.group_block_type_inventory_transfers_expeditions")
        if block_transfer_expedition:
            picking_type = self.env["stock.picking.type"].search([("id", "=", vals[0]["picking_type_id"])]) if vals else self.picking_type_id
            if picking_type.code == "outgoing":
                raise UserError(_("You do not have permission to make shipment-type transfers"))
