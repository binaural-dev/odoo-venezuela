from odoo import api, models, fields, _
from odoo.exceptions import UserError, ValidationError


class FeesRetentionBinaural(models.Model):
    _name = "fees.retention"
    _description = "Fees"

    name = fields.Char(string="Description", required=True, store=True)
    percentage = fields.Float(string="Fees percentage", store=True)
    subtract_money = fields.Float(string="Quantity to subtract to fees", store=True)
    amount_subtract = fields.Float(
        string="Subtract mount", compute="_compute_amount_subtract", store=True
    )
    apply_subtracting = fields.Boolean(string="Subtract apply?", default=False, store=True)
    accumulated_rate = fields.Boolean(string="Rate accumulated?", default=False, store=True)
    status = fields.Boolean(default=True, string="Is active?")
    tax_unit_ids = fields.Many2one(
        "tax.unit", string="Tax Unit", required=True, domain=[("status", "=", True)]
    )
    accumulated_rate_ids = fields.One2many(
        comodel_name="accumulated.fees", inverse_name="fees_id", string="Accumulated fees"
    )

    @api.constrains("accumulated_rate_ids", "percentage")
    def _check_data_accumulated(self):
        if self.accumulated_rate and not len(self.accumulated_rate_ids):
            raise ValidationError(_("You must enter the accumulated fees.\n"))
        if self.percentage < 0:
            raise ValidationError(_("The rate percentage cannot be negative.\n"))

    @api.depends("apply_subtracting", "percentage", "tax_unit_ids")
    def _compute_amount_subtract(self):
        for record in self:
            if record.apply_subtracting:
                record.amount_subtract = (
                    record.tax_unit_ids.value * 83.3334 * record.percentage / 100
                )
            else:
                record.amount_subtract = 0

    @api.onchange("percentage")
    def onchange_percentage(self):
        if self.percentage > 100:
            return {
                "warning": {
                    "title": _("Error in the fees percentage field"),
                    "message": _("The percentage of fees cannot be greater than 100%.\n"),
                },
                "value": {"percentage": 0},
            }
