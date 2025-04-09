from odoo import fields, models

class ResCompany(models.Model):
    _inherit = "res.company"
    
    username_tfhka = fields.Char()
    password_tfhka = fields.Char()
    url_tfhka = fields.Char()
