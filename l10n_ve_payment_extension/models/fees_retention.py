import logging
from odoo import api, models, fields, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class FeesRetention(models.Model):
    _name = "fees.retention"
    _description = "Fees"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(string="Description", required=True, store=True)
    percentage = fields.Float(string="Fees percentage", store=True)
    subtract_money = fields.Float(string="Quantity to subtract to fees", store=True)
    amount_subtract = fields.Float(
        string="Subtract mount", compute="_compute_amount_subtract", store=True
    )
    apply_subtracting = fields.Boolean(string="Subtract apply?", default=False, store=True)
    accumulated_rate = fields.Boolean(string="Rate accumulated?", default=False, store=True)
    status = fields.Boolean(default=True, string="Is active?", tracking=True)
    tax_unit_ids = fields.Many2one(
        "tax.unit", string="Tax Unit", required=True, domain=[("status", "=", True)],tracking=True
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

    @api.constrains("accumulated_rate", "accumulated_rate_ids")
    def _check_accumulated_tiers_continuity(self):
        """Every tier but the last needs an upper limit, and limits must grow.

        The tier is picked by its upper limit (`stop`), so a missing or
        out-of-order limit would leave a base amount without a tier.
        """
        for record in self.filtered("accumulated_rate"):
            tiers = record.accumulated_rate_ids.sorted("start")
            previous_stop = 0.0
            for tier in tiers[:-1]:
                if tier.stop <= previous_stop:
                    raise ValidationError(
                        _(
                            "Tier '%(name)s' must have an upper limit greater than the "
                            "previous tier's, otherwise some amounts would have no rate.",
                            name=tier.name,
                        )
                    )
                previous_stop = tier.stop
            if tiers and tiers[-1].stop:
                raise ValidationError(
                    _("The last tier must have no upper limit (leave 'stop' empty).")
                )

    def get_accumulated_rate(self, base_ut):
        """Return the accumulated tier (accumulated.fees) that applies to `base_ut`.

        Tiers are contiguous: a tier covers everything above the previous
        tier's `stop` up to its own `stop` (inclusive), and the tier without
        `stop` is open-ended. `start` is only informative, so a configuration
        such as 0-2000 / 2001-3000 does not leave 2000 < base < 2001 uncovered
        (Decreto 1.808, art. 9 parágrafo primero: "hasta", "entre ... hasta",
        "por el monto que exceda de").

        :param float base_ut: taxable base expressed in tax units
        :return: the matching tier, or an empty recordset if base_ut < 0
        """
        self.ensure_one()
        if base_ut < 0:
            return self.env["accumulated.fees"]
        for tier in self.accumulated_rate_ids.sorted("start"):
            if not tier.stop or base_ut <= tier.stop:
                return tier
        return self.env["accumulated.fees"]

    @api.depends("apply_subtracting", "percentage", "tax_unit_ids", "tax_unit_ids.value")
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
