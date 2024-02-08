import logging

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools.float_utils import float_compare

_logger = logging.getLogger(__name__)


class CommissionPolicyLine(models.Model):
    _name = "commission.policy.line"
    _description = "Commission percentage based in a certain range date"

    date_from = fields.Integer(required=True, default=1)
    date_to = fields.Integer(required=True)
    commission = fields.Float(required=True, help="Commission percentage")
    percentage_report = fields.Float(
        "Percentage for Reports", help="Commission percentage of reports"
    )
    not_applied = fields.Boolean(
        "Do not apply to the report", help="Do not apply this restriction to the report"
    )
    policy_id = fields.Many2one("commission.policy", required=True, ondelete="cascade")
    policy_type = fields.Selection(related="policy_id.policy_type")

    @api.constrains("commission")
    def _check_commission_non_negative(self):
        for commission_line in self:
            if float_compare(commission_line.commission, 0.0, precision_digits=2) < 0:
                raise ValidationError(_("The commission cannot be lower than zero!"))
