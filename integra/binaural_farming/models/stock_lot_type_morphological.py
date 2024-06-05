from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

class StockLotTypeMorphological(models.Model):
    _name = 'stock.lot.type.morphological'

    
    # fields models
    name = fields.Char()
    types_morphological = fields.Char()
