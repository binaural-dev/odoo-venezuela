from odoo import models, fields

class ResGroups(models.Model):
    _inherit = 'res.groups'

    sale_note = fields.Boolean(
        string = "Can see sale note", 
        default=False
    )