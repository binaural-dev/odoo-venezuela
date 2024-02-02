from odoo import api, fields, models, _


class HrPayrollMove(models.Model):
    _name = "hr.payroll.move"
    _description = "Payslip Payments"
    _rec_name = "employee_name"
    _check_company_auto = True
    _inherit = ["mail.thread"]

    company_id = fields.Many2one("res.company")
    move_type = fields.Selection(
        [
            ("salary", "Salary"),
            ("vacation", "Vacations"),
            ("benefits", "Benefits"),
            ("profit_sharing", "Profit Sharing"),
            ("liquidation", "Liquidation"),
            ("advance", "Advance"),
        ],
        string="Type",
        default="salary",
    )
    employee_id = fields.Many2one("hr.employee", required=True)
    employee_name = fields.Char(string="Name", related="employee_id.name", store=True)
    employee_prefix_vat = fields.Selection(related="employee_id.prefix_vat", store=True)
    employee_vat = fields.Char(string="Document", related="employee_id.vat", store=True)
    employee_job_id = fields.Many2one("hr.job", related="employee_id.job_id")
    date = fields.Date(string="Payslip Date", default=fields.Date.today())
    department_id = fields.Many2one(
        "hr.department", related="employee_id.department_id", store=True
    )

    total_basic = fields.Float(string="Basic salary")
    total_deduction = fields.Float()
    total_accrued = fields.Float()
    total_net = fields.Float()

    total_assig = fields.Float()
    advance_of_benefits = fields.Float()
    benefits_payment = fields.Float()
    profit_sharing_payment = fields.Float()

    date_from_vacation = fields.Date()
    date_to_vacation = fields.Date()

    vacational_period = fields.Char(compute="_compute_vacational_period")
    vacation_days = fields.Integer()
    vacation_bonus_days = fields.Integer()
    consumed_vacation_days = fields.Integer()
    total_vacation_bonus = fields.Float()
    total_vacation = fields.Float()

    @api.depends("date_from_vacation", "date_to_vacation")
    def _compute_vacational_period(self):
        for move in self:
            if not (bool(move.date_from_vacation) and bool(move.date_to_vacation)):
                move.vacational_period = ""
                continue
            move.vacational_period = (
                f"{move.date_from_vacation.strftime('%d/%m/%Y')}"
                f"- {move.date_to_vacation.strftime('%d/%m/%Y')}"
            )
