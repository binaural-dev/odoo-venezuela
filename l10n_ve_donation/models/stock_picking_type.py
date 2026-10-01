from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

import logging

_logger = logging.getLogger(__name__)

class StockPickingType(models.Model):
    _inherit = "stock.picking.type"

    is_donation_picking_type = fields.Boolean(
        string="Donation Picking Type",
        help="Shared flag: marks this operation type as part of a donation "
        "flow, either outgoing (donation given) or incoming (donation "
        "received). Each module that implements donations determines its "
        "own direction by checking the native `code` of the operation type, "
        "not a separate field per direction.",
    )

    @api.constrains("is_donation_picking_type", "code")
    def _check_donation_picking_type(self):
        for record in self:
            if record.is_donation_picking_type and record.code not in ("incoming", "outgoing"):
                raise ValidationError(_("Donation picking type must be incoming or outgoing"))
