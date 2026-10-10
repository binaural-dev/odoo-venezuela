from odoo import fields, models


class FleetVehicle(models.Model):
    _inherit = "fleet.vehicle"

    is_trailer = fields.Boolean(
        string="Is a Trailer",
        help="Mark it for trailers. They are offered in the 'Trailer' field of "
        "dispatch guides instead of the 'Vehicle' field.",
    )
