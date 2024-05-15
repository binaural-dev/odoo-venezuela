from odoo import api, fields, models, _

class HrPayrollStructureType(models.Model):
    _inherit = "hr.payroll.structure.type"

    active = fields.Boolean(string='Active', default=True)