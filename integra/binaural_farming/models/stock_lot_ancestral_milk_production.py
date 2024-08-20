from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

class StockLotAncestralMilkProduction(models.Model):
    _name = 'stock.lot.ancestral.milk.production'
    _description = 'Ancestral milk production'
    
    # fields models
    name = fields.Selection(
        [
         ('mother','Mother'),
         ('maternal_grandmother','Maternal Grandmother'),
         ('paternal_grandmother','Paternal Grandmother')
        ]
    )
    # Muestra del dia
    first_day_sample = fields.Integer()
    second_day_sample = fields.Integer()
    third_day_sample = fields.Integer()
    # Muestras de litros de leche
    first_milk_sample = fields.Float(digits='Stock Weight')
    second_milk_sample = fields.Float(digits='Stock Weight')
    third_milk_sample = fields.Float(digits='Stock Weight')

    lot_id = fields.Many2one(
        'stock.lot'
    )