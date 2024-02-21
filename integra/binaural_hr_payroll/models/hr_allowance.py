from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HrAllowance(models.Model):
    _name = "hr.allowance"
    _description = "Salary Allowances"

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    active = fields.Boolean(default=True)
    value = fields.Float(required=True)
    description = fields.Char(required=True)
    line_ids = fields.One2many("hr.allowance.line", "allowance_id")

    _sql_constraints = [
        ("name_unique", "UNIQUE(name)", _("There is an allowance with that name already.")),
        ("code_unique", "UNIQUE(code)", _("There is an allowance with that name already.")),
    ]

    def toggle_active(self):
        for allowance in self:
            if not allowance.active:
                return super().toggle_active()
            if any(line.employee_id for line in allowance.line_ids):
                raise UserError(
                    _("You can't disable this allowance because it's binded to an employee.")
                )
            return super().toggle_active()

    def action_update_lines(self):
        for line in self.mapped("line_ids"):
            line.action_update_value()


class HrAllowanceLine(models.Model):
    _name = "hr.allowance.line"
    _description = "Salary Allowances line"

    allowance_id = fields.Many2one("hr.allowance")
    name = fields.Char(compute="_compute_name")
    code = fields.Char(related="allowance_id.code", store=True)
    employee_id = fields.Many2one("hr.employee")
    employee_vat = fields.Char(string="Employee VAT", related="employee_id.vat")
    value = fields.Float(compute="_compute_value", readonly=False, store=True)
    description = fields.Char(related="allowance_id.description")

    @api.depends("allowance_id")
    def _compute_name(self):
        for line in self:
            allowance = line.allowance_id
            line.name = f"{allowance.name} ({allowance.code}) - {line.employee_id.name}"

    @api.depends("allowance_id")
    def _compute_value(self):
        for line in self:
            line.action_update_value()

    def action_update_value(self):
        for line in self:
            line.value = line.allowance_id.value
