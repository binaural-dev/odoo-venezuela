from odoo import fields, models, _, api
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class HikcentralDepartment(models.Model):
    _inherit = "hikcentral.department"

    default_membership_dept = fields.Boolean(
        string="Default Membership Department",
        help="If checked, this department will be used by default when creating member users.",
    )

    @api.constrains("default_membership_dept")
    def _check_single_default_membership_dept(self):
        for record in self:
            if record.default_membership_dept:
                existing_defaults = self.search(
                    [("default_membership_dept", "=", True), ("id", "!=", record.id)]
                )
                if existing_defaults:
                    raise ValidationError(
                        _(
                            "Only one department can be set as the default membership department."
                        )
                    )
