from odoo import models, fields, api
from odoo.http import request

class ResCompany(models.Model):
    _inherit = "res.company"

    budget_send = fields.Boolean()
