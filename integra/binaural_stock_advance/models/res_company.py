from odoo import api, fields, models, _


class ResCompany(models.Model):
    _inherit = "res.company"

    check_advance_stock = fields.Boolean(default="False")
    
