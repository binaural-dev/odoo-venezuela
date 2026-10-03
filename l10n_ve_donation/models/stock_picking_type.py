from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

import logging

_logger = logging.getLogger(__name__)

class StockPickingType(models.Model):
    _inherit = "stock.picking.type"

    is_donation_picking_type = fields.Boolean(
        string="Donation Picking Type",
        help="Only filters the operation types offered in the form of the "
        "Inventory > Operations > Donations menu. It does not activate any "
        "donation logic by itself: a picking is a donation only when its "
        "`Is Donation` field is set (by that menu, or by a donation sale).",
    )

    @api.constrains("is_donation_picking_type", "code")
    def _check_donation_picking_type(self):
        for record in self:
            if record.is_donation_picking_type and record.code not in ("incoming", "outgoing"):
                raise ValidationError(_("Donation picking type must be incoming or outgoing"))
