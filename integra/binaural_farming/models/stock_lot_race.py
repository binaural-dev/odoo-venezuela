from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

class StockLotRace(models.Model):
    _name = 'stock.lot.race'
    _description = 'Manage race'
    _rec_name = 'description'

    # fields models
    description = fields.Char()
    active = fields.Boolean(default=True)
