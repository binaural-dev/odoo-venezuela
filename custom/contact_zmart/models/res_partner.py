from odoo import models, fields, api, _

class ResPartner(models.Model):
    _inherit = "res.partner"

    sales_area = fields.Many2one('res.partner.sale')
    rif = fields.Binary()
    commercial_register = fields.Binary()