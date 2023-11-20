from odoo import models, fields, api, _

class HrEmployeePublic(models.Model):
    _inherit = 'hr.employee.public'

    is_seller = fields.Boolean(string='Is a Seller')