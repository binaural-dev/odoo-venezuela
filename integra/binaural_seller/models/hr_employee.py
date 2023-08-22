from odoo import models, fields, api, _

class HrEmployee(models.Model):
    _inherit = 'hr.employee'


    is_seller = fields.Boolean(string='Is a Seller')