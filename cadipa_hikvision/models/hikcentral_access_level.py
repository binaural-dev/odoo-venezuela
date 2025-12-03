from odoo import fields, models, api, _
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)


class HikcentralAccessLevel(models.Model):
    _inherit = "hikcentral.access.level"

    default_membership_access_level = fields.Boolean(
        string="Default Membership Access Level",
        help="If checked, this access level will be assigned to new members by default.",
    )

    @api.constrains("default_membership_access_level")
    def _check_single_default_membership_access_level(self):
        for record in self:
            if record.default_membership_access_level:
                existing_defaults = self.search(
                    [
                        ("default_membership_access_level", "=", True),
                        ("id", "!=", record.id),
                    ]
                )
                if existing_defaults:
                    raise ValidationError(
                        _(
                            "Only one access level can be set as the default visitor access level."
                        )
                    )
