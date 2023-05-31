from odoo import models, fields

class Users(models.Model):
    _inherit = 'res.users'

    authorized_discount_pos = fields.Boolean(
        'authorized personnel to use discount in pos')
