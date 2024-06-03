from odoo import api, fields, models, _

class HrSalaryRuleCategory(models.Model):
    _inherit = "hr.salary.rule.category"
    
    active = fields.Boolean(string='Active', default=True)