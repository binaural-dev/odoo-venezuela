from odoo import models, fields, api
from odoo.http import request

class ResCompany(models.Model):
    _inherit = "res.company"

    initial_seller = fields.Many2one('hr.employee')

    multiple_sellers = fields.Boolean()

    restrict_seller = fields.Boolean()

    company_seller = fields.Boolean()
