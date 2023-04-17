from odoo import models, fields, api, _

class IotBox(models.Model):
    _inherit = 'iot.box'

    ip_public = fields.Char(string='Public IP Address', default=False)
