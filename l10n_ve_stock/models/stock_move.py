from odoo import _, api, fields, models
from odoo.exceptions import UserError

import logging
_logger = logging.getLogger(__name__)

class StockMove(models.Model):
    _inherit = "stock.move"
    _order = "priority_location asc"

    priority_location = fields.Integer(
        string="Priority", related="product_id.priority_location", store=True
    )

    @api.model
    def default_get(self, fields):
        self.validate_block_add_line_expedition()
        return super(StockMove, self).default_get(fields)
    
    def validate_block_add_line_expedition(self):  
        
        block_transfer_expedition = self.env.user.has_group("l10n_ve_stock.group_block_type_inventory_transfers_expeditions")

        if "default_picking_id" in self.env.context:
            if block_transfer_expedition:
                
                picking_type = (
                    self.env["stock.picking.type"].search(
                        [("id", "=", self.env.context.get("picking_type_id", False))]
                    )

                    if self.env.context.get("picking_type_id", False)
                    else self.picking_type_id
                )

                if picking_type and picking_type.code == "outgoing":
                    raise UserError(_("You do not have permission to add lines to this transfer."))

    @api.onchange('quantity_done')
    def _onchange_quantity_done(self):
        for record in self:
            self._validate_transfer_quantity(record)

            

    def _validate_transfer_quantity(self, record):
            if self.env.company.validate_without_product_quantity:
                return

            if record.quantity_done > record.forecast_availability:
                record.quantity_done = 0
                raise UserError(_("You cannot make transfers larger than the demand."))
