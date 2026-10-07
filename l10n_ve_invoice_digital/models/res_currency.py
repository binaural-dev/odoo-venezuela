from odoo import fields, models

class ResCurrency(models.Model):
    _inherit = 'res.currency'

    code_tfhka = fields.Char(string='Code TFHKA', help='This is the currency code that is sent when scanning a document.')