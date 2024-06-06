from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

class StockLotRace(models.Model):
    _name = 'stock.lot.race'
    _description = 'Manage race'


    # fields models
    name = fields.Char()
    description = fields.Char()
    active = fields.Boolean()
