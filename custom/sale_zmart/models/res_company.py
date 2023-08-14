from odoo import models, fields, api, _

class ResCompany(models.Model):
    _inherit = "res.company"

    logo_2 = fields.Binary(string="Company Logo", readonly=False)