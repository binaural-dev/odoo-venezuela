import logging

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools.float_utils import float_compare

_logger = logging.getLogger(__name__)


class CommissionPolicyLine(models.Model):
    _name = "commission.policy.line"
    _description = "Commission percentage based in a certain range date"
    _order = "date_from asc"

    date_from = fields.Integer(required=True, default=0)
    date_to = fields.Integer(required=True)
    commission = fields.Float(required=True, help="Commission percentage")
    policy_id = fields.Many2one("commission.policy", required=True, ondelete="cascade")
    policy_type_id = fields.Many2one("commission.policy.type", related="policy_id.policy_type_id")
    policy_type = fields.Selection(related="policy_id.policy_type")
    infinite = fields.Boolean()

    @api.constrains("commission")
    def _check_commission_non_negative(self):
        for commission_line in self:
            if float_compare(commission_line.commission, 0.0, precision_digits=2) < 0:
                raise ValidationError(_("The commission cannot be lower than zero!"))

    @api.onchange("infinite")
    def _onchange_infinite(self):
        if self.infinite:
            self.date_to = False

    def _prepare_commission_line_image(self):
        lines = []
        for record in self:
            lines.append( {
                "date_from": record.date_from,
                "date_to": record.date_to,
                "commission": record.commission,
                "policy_type_id": record.policy_type_id.id,
                "infinite": record.infinite,
            })
        return lines

    @api.constrains("date_from", "date_to", "infinite")
    def _check_date_range(self):
        dates = []
        for line in self.policy_id.commission_line_ids:
            if line.date_from > line.date_to and not line.infinite:
                raise ValidationError(_("The date from must be lower than the date to!"))

            if not dates:
                dates.append(line.date_from)
                dates.append(line.date_to)
                continue

            max_date = max(dates)
            min_date = min(dates)

            if line.date_from >= min_date and line.date_from <= max_date:
                raise ValidationError(_("The date range must not overlap!"))

            if line.infinite and not line.date_to:
                continue

            if line.date_to <= max_date and line.date_to >= min_date:
                raise ValidationError(_("The date range must not overlap!"))

            dates.append(line.date_from)
            dates.append(line.date_to)
