from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

class StockLotBreeder(models.Model):
    _name = "stock.lot.breeder"
    # fields models
    name = fields.Char()
