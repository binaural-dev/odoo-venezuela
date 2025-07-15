from odoo import models, fields

class ResCompany(models.Model):
    _inherit = "res.company"

    display_consumables = fields.Boolean()