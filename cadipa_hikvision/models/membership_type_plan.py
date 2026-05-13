from odoo import models, api, exceptions, fields, _
from dateutil.relativedelta import relativedelta
from odoo.exceptions import ValidationError
import datetime
import logging

_logger = logging.getLogger(__name__)


class MembershipTypePlan(models.Model):
    _inherit = "membership.type.plan"

    hikcentral_department_id = fields.Many2one(
        "hikcentral.department",
        help="The Hikcentral department associated with this membership type plan.",
    )
    hikcentral_access_level_ids = fields.Many2many(
        "hikcentral.access.level",
        string="HikCentral Access Levels",
        help="Access levels assigned to members of this plan by default.",
    )
