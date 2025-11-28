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
