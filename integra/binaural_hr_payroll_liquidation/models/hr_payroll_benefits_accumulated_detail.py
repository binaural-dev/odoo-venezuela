from odoo import fields, models


class HrPayrollBenefitAccumulatedDetail(models.Model):
    """
    This model is used for keeping track of all the registered payrroll benefits accumulation.

    Its records are created inside the _get_benefits() methods on the inherit of the employee model
    on this same module.
    """

    _name = "hr.payroll.benefits.accumulated.detail"
    _description = "Payroll Benefits Accumulated Detail"

    date = fields.Date()
    employee_id = fields.Many2one("hr.employee")
    employee_vat = fields.Char(related="employee_id.vat")
    employee_department_id = fields.Many2one("hr.department", related="employee_id.department_id")
    employee_job_id = fields.Many2one("hr.job", related="employee_id.job_id")
    amount = fields.Float()
    accumulated_amount = fields.Float()
    foreign_amount = fields.Float()
    foreign_accumulated_amount = fields.Float()
    type = fields.Selection(
        [
            ("monthly", "Monthly"),
            ("quarterly", "Quarterly"),
            ("annual", "Annual"),
        ]
    )
