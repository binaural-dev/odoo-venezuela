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

    @api.constrains(
        "is_donation_picking_type", "code", "warehouse_id", "default_location_dest_id"
    )
    def _check_donation_picking_type(self):
        """A donation operation type must be incoming or outgoing. An
        outgoing one is the donation delivery: the journal entry of its
        pickings is determined by the configuration, so it must belong to the
        donation warehouse and its default destination must be an `inventory`
        location. The incoming valuation account of that location is not
        required here: the picking validation requires it, only for
        real_time products.

        When an operation type is created Odoo precomputes Customers as the
        default destination of an outgoing type, so for an outgoing donation
        type the user must set an `inventory` destination explicitly. An empty
        destination is not checked: the picking validation covers the real
        destination."""
        for record in self:
            if not record.is_donation_picking_type:
                continue
            if record.code not in ("incoming", "outgoing"):
                raise ValidationError(_("Donation picking type must be incoming or outgoing"))
            if record.code != "outgoing":
                continue
            warehouse = record.warehouse_id
            if not warehouse or not warehouse.is_donation_warehouse:
                raise ValidationError(_(
                    "The donation delivery operation type %(picking_type)s must belong to a "
                    "donation warehouse. Set the Warehouse field of the operation type to the "
                    "donation warehouse.",
                    picking_type=record.display_name,
                ))
            location = record.default_location_dest_id
            if not location:
                continue
            if location.usage != "inventory":
                raise ValidationError(_(
                    "The Default Destination Location %(location)s of the donation delivery "
                    "operation type %(picking_type)s is not of type Inventory Loss. Change the "
                    "Default Destination Location of the operation type to an Inventory Loss "
                    "location.",
                    location=location.display_name,
                    picking_type=record.display_name,
                ))
