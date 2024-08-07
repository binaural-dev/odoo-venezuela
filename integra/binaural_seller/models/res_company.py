from odoo import models, fields, api
from odoo.http import request

class ResCompany(models.Model):
    _inherit = "res.company"

    initial_seller = fields.Many2one('hr.employee')

    multiple_sellers = fields.Boolean()

    restrict_seller = fields.Boolean()

    company_seller = fields.Boolean()

    @api.onchange("company_seller")
    def _onchange_company_seller(self):
        if not self.company_seller:
            self.write({"company_seller": False})