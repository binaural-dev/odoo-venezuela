from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

import logging

_logger = logging.getLogger(__name__)

class StockPickingType(models.Model):
    _inherit = "stock.picking.type"

    is_donation_picking_type = fields.Boolean(
        string="Donation Picking Type",
    )
    @api.constrains("is_donation_picking_type", "code")
    def _check_donation_picking_type(self):
        for record in self:
            if record.is_donation_picking_type and record.code != "outgoing":
                raise ValidationError(_("Donation picking type must be outgoing"))
