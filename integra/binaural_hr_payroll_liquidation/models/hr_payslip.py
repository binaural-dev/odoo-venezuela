from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class HrPayslip(models.Model):
    _inherit = "hr.payslip"

    is_benefits = fields.Boolean(compute="_compute_is_benefits")
    benefits_advance = fields.Float(
        string="Advance",
        readonly=True,
        states={"draft": [("readonly", False)], "verify": [("readonly", False)]},
    )
    foreign_benefits_advance = fields.Float(
        string="Foreign Advance",
        readonly=True,
        store=True,
        compute="_compute_foreign_benefits_advance",
        inverse="_inverse_foreign_benefits_advance",
        states={"draft": [("readonly", False)], "verify": [("readonly", False)]},
    )
    benefits_advance_percentage = fields.Float(
        string="Advance Percentage",
        readonly=True,
        store=True,
        compute="_compute_benefits_advance_percentage",
        inverse="_inverse_benefits_advance_percentage",
        states={"draft": [("readonly", False)], "verify": [("readonly", False)]},
    )

    @api.depends("struct_id")
    def _compute_is_benefits(self):
        for payslip in self:
            payslip.is_benefits = payslip.struct_id.category == "benefits"

    @api.depends("benefits_advance", "foreign_inverse_rate")
    def _compute_foreign_benefits_advance(self):
        for payslip in self:
            payslip.foreign_benefits_advance = (
                payslip.benefits_advance * payslip.foreign_inverse_rate
            )

    def _inverse_foreign_benefits_advance(self):
        for payslip in self:
            if not payslip.foreign_inverse_rate:
                continue
            payslip.benefits_advance = (
                payslip.foreign_benefits_advance / payslip.foreign_inverse_rate
            )

    @api.depends("benefits_advance")
    def _compute_benefits_advance_percentage(self):
        for payslip in self:
            benefits_available_amount = payslip._get_employee_benefits_available_amount()
            _logger.warning("Benefits available amount: %s", benefits_available_amount)
            if benefits_available_amount == 0:
                payslip.benefits_advance_percentage = 0
                continue
            payslip.benefits_advance_percentage = (
                payslip.benefits_advance * 100 / benefits_available_amount
            )

    def _inverse_benefits_advance_percentage(self):
        for payslip in self:
            if not payslip.is_benefits:
                payslip.benefits_advance = 0
                continue
            benefits_available_amount = payslip._get_employee_benefits_available_amount()
            if benefits_available_amount == 0:
                payslip.benefits_advance = 0
                continue
            payslip.benefits_advance = benefits_available_amount * (
                payslip.benefits_advance_percentage / 100
            )

    def compute_sheet(self):
        """
        Adds validation so the user cannot compute the sheet of a payslip with a benefits advance
        payment greater than the 75% of the available amount for the employee.
        """
        for slip in self:
            if not slip.is_benefits:
                continue
            if slip.benefits_advance_percentage == 0 or slip.benefits_advance == 0:
                raise UserError(
                    _(
                        "You cannot make a benefits advance to an employee who doesn't have"
                        " available benefits."
                    )
                )

            if slip.benefits_advance_percentage > 75:
                raise UserError(
                    _(
                        "You cannot make a benefits advance payment of more than the 75% of the"
                        " available amount for the employee."
                    )
                )
        return super().compute_sheet()

    def action_payslip_done(self):
        """
        Make the benefits advance entry for each payslip after they're confirmed.
        """
        res = super().action_payslip_done()
        for slip in self:
            _logger.warning(
                "Fractional Vacation Days: %s", slip.employee_id.get_fractional_vacation_days()
            )

            slip.employee_id._register_payroll_benefits(
                benefits_advance=(slip.benefits_advance, slip.foreign_benefits_advance)
            )
        return res

    def _get_employee_benefits_available_amount(self):
        self.ensure_one()
        benefits_accumulated = self.env["hr.payroll.benefits.accumulated"].search(
            [
                ("employee_id", "=", self.employee_id.id),
            ],
            limit=1,
        )
        return benefits_accumulated.available_benefits or 0

    def _get_base_local_dict(self):
        localdict = super()._get_base_local_dict()
        localdict.update(
            {
                "dias_prestaciones_mes_config": self.company_id.benefits_days_per_month,
                "tipo_calculo_intereses_prestaciones_config": (
                    self.company_id.benefits_interest_computation_type
                ),
            }
        )
        return localdict
