from odoo import api, fields, models


class HrPayslipLine(models.Model):
    _inherit = "hr.payslip.line"

    foreign_currency_id = fields.Many2one(related="slip_id.foreign_currency_id")

    foreign_amount = fields.Monetary(currency_field="foreign_currency_id")
    foreign_total = fields.Monetary(
        compute="_compute_foreign_total", store=True, currency_field="foreign_currency_id"
    )

    employee_name = fields.Char(related="employee_id.name")
    employee_vat = fields.Char(related="employee_id.vat")
    employee_job_id = fields.Many2one("hr.job", related="employee_id.job_id")
    employee_department_id = fields.Many2one(
        "hr.department", string="Departament", related="employee_id.department_id"
    )
    category_code = fields.Char(related="category_id.code")
    slip_state = fields.Selection(related="slip_id.state")

    @api.depends("quantity", "amount", "rate")
    def _compute_foreign_total(self):
        for line in self:
            line.foreign_total = float(line.quantity) * line.foreign_amount * line.rate / 100

    def get_values_for_payroll_move(self):
        """
        Retrieves and returns a dictionary of payroll move parameters based on the
        category and specific code of the payroll line.

        This method ensures that only one payroll line is being processed. It uses
        predefined mappings to update the result dictionary with values corresponding
        to the payroll line's category code and specific code.

        Returns
        -------
        dict
            A dictionary containing the payroll move parameters with keys as
            defined by the category and specific code mappings.

        Raises
        ------
        ValidationError
            If more than one payroll line is being processed.

        Examples
        --------
        >>> line = self.env['hr.payslip.line'].browse(1)
        >>> line.category_id.code = 'BASIC'
        >>> line.total = 150.0
        >>> line.foreign_total = 15.0
        >>> line.get_values_for_payroll_move()
        {'total_basic': 150.0, 'foreign_total_basic': 15.0}

        >>> line.category_id.code
        'DED'
        >>> line.total
        100.0
        >>> line.foreign_total
        10.0
        >>> line.get_values_for_payroll_move()
        {'total_deduction': 100.0, 'foreign_total_deduction': 10.0}
        """
        self.ensure_one()

        result = {}

        # Define mappings for category_id and code
        category_mappings = {
            "DED": {"total_deduction": "total", "foreign_total_deduction": "foreign_total"},
            "ASIG": {"total_assig": "total", "foreign_total_assig": "foreign_total"},
            "BASIC": {"total_basic": "total", "foreign_total_basic": "foreign_total"},
            "DEV": {"total_accrued": "total", "foreign_total_accrued": "foreign_total"},
            "NET": {"total_net": "total", "foreign_total_net": "foreign_total"},
        }

        code_mappings = {
            "PVAC": {
                "vacation_days": "quantity",
                "total_vacation": "total",
                "foreign_total_vacation": "foreign_total",
            },
            "BVAC": {
                "vacation_bonus_days": "quantity",
                "total_vacation_bonus": "total",
                "foreign_total_vacation_bonus": "foreign_total",
            },
            "DDVM": {"consumed_vacation_days": "total"},
            "UTIL": {
                "profit_sharing_payment": "total",
                "foreign_profit_sharing_payment": "foreign_total",
            },
            "ADPRESTA": {
                "advance_of_benefits": "total",
                "foreign_advance_of_benefits": "foreign_total",
            },
        }

        # Update result based on category_id.code
        if self.category_id.code in category_mappings:
            for key, attr in category_mappings[self.category_id.code].items():
                result[key] = getattr(self, attr)

        # Update result based on code
        if self.code in code_mappings:
            for key, attr in code_mappings[self.code].items():
                result[key] = getattr(self, attr)

        return result
