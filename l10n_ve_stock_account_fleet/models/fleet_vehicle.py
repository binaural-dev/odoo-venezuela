from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class FleetVehicle(models.Model):
    _inherit = "fleet.vehicle"

    is_trailer = fields.Boolean(
        string="Is a Trailer",
        help="Mark it for trailers. They are offered in the 'Trailer' field of "
        "dispatch guides instead of the 'Vehicle' field.",
    )

    @api.constrains("driver_id", "future_driver_id")
    def _check_driver_is_not_company(self):
        for vehicle in self:
            for fname in ("driver_id", "future_driver_id"):
                partner = vehicle[fname]
                if partner and partner.is_company:
                    raise ValidationError(
                        _(
                            "The driver of a vehicle must be a person, not a "
                            "company: '%s'."
                        )
                        % partner.name
                    )
