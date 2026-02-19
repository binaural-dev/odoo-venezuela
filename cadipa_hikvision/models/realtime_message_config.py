from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class RealtimeMessageConfig(models.Model):
    _name = "realtime.message.config"
    _description = "Realtime Message Configuration"
    _order = "code"

    code = fields.Char(
        string="Code",
        help="Unique code identifier (1, 2, 3)",
    )

    name = fields.Char(
        string="Name",
        help="Descriptive name of the status",
    )

    message = fields.Text(
        string="Message",
        help="Message to display on screen",
    )

    color = fields.Char(
        string="Color",
        help="Color in hexadecimal format (e.g. #27ae60)",
    )

    duration_ms = fields.Integer(
        string="Duration (ms)",
        default=5000,
        help="Message duration in milliseconds",
    )

    device_ids = fields.Many2many(
        "hikcentral.device",
        string="Devices",
        help="Associated devices (minimum 1 required when saving)",
    )
    condition_description = fields.Text(
        string="Condition Description",
        help="Description of the condition (for future reference)",
    )

    _sql_constraints = [
        (
            "code_unique",
            "unique(code)",
            _("The code must be unique."),
        ),
    ]

    @api.constrains("device_ids")
    def _check_at_least_one_device(self):
        """Ensure at least one device is associated (only on write, not on create)."""
        if self.env.context.get("skip_device_validation"):
            return
        pass

    @api.model
    def create(self, vals):
        """Prevent creation of new records. Only the 3 predefined records are allowed."""
        existing_count = self.search_count([])
        if existing_count >= 3:
            raise ValidationError(
                _(
                    "Cannot create new records. Only the 3 predefined configurations are allowed. "
                    "You can only modify existing records."
                )
            )
        return super().create(vals)

    def unlink(self):
        """Prevent deletion of records."""
        raise ValidationError(
            _(
                "Cannot delete configuration records. You can only modify existing records."
            )
        )

    def write(self, vals):
        """Allow modification of existing records."""
        result = super().write(vals)
        if "device_ids" in vals:
            for record in self:
                if not record.device_ids:
                    raise ValidationError(
                        _("At least one device must be associated with the configuration.")
                    )
        return result
