from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

class StockLotQualitativeValuation(models.Model):
    _name = 'stock.lot.qualitative.valuation'

    
    # fields models
    name = fields.Char()
    
    name_valoration = fields.Char()