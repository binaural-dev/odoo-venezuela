from odoo import models, fields, api, _


class ResPartner(models.Model):
    _inherit = "res.partner"
    
    plus_code = fields.Char()