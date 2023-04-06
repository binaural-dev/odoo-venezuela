from odoo import models, fields, api
class Brand(models.Model):
    _name = 'product.brand'
    _description = 'Brands'

    active = fields.Boolean( 
        default=True
    )
    name = fields.Char(
        required=True,
        help='Brand name'
    )