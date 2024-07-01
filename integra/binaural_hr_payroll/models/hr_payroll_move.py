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
            ("profit_sharing", "Profit Sharing"),
            ("advance", "Advance"),
        ],
        string="Type",
        default="salary",
    )
    slip_id = fields.Many2one("hr.payslip")
    employee_id = fields.Many2one(
        "hr.employee", compute="_compute_payslip_fields", store=True, readonly=False
    )
    employee_name = fields.Char(
        string="Name", compute="_compute_payslip_fields", store=True, readonly=False
    )
    employee_vat = fields.Char(
        string="Document", compute="_compute_payslip_fields", store=True, readonly=False
    )
    employee_job_id = fields.Many2one("hr.job", compute="_compute_payslip_fields", readonly=False)
    date = fields.Date(string="Payslip Date", default=fields.Date.today())
    department_id = fields.Many2one(
        "hr.department", compute="_compute_payslip_fields", store=True, readonly=False
    )

    total_basic = fields.Float(string="Basic salary")
    total_deduction = fields.Float()
    total_accrued = fields.Float()
    total_net = fields.Float()

    total_assig = fields.Float()
    profit_sharing_payment = fields.Float()

    date_from_vacation = fields.Date()
    date_to_vacation = fields.Date()

    vacational_period = fields.Char(compute="_compute_vacational_period", store=True)
    vacation_days = fields.Integer()
    vacation_bonus_days = fields.Integer()
    consumed_vacation_days = fields.Integer()
    total_vacation_bonus = fields.Float()
    total_vacation = fields.Float()

    # Foreign Amounts
    foreign_total_basic = fields.Float(string="Foreign Basic salary")
    foreign_total_deduction = fields.Float()
    foreign_total_accrued = fields.Float()
    foreign_total_net = fields.Float()

    foreign_total_assig = fields.Float()
    foreign_profit_sharing_payment = fields.Float()

    foreign_total_vacation_bonus = fields.Float()
    foreign_total_vacation = fields.Float()

    @api.depends("slip_id")
    def _compute_payslip_fields(self):
        for move in self.filtered(lambda m: m.slip_id):
            move.employee_id = move.slip_id.employee_id
            move.employee_vat = move.employee_id.vat
            move.employee_job_id = move.employee_id.job_id
            move.department_id = move.employee_id.department_id

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
