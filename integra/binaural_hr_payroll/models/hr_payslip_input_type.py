from odoo import api, fields, models, _

class HrPayslipInputType(models.Model):
    _inherit = "hr.payslip.input.type"

    active = fields.Boolean(string='Active', default=True)