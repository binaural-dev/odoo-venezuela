from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

class StockLotWeightOffspring(models.Model):
    _name = 'stock.lot.weight.offspring'
    _description = 'Weight Offspring'
    
    # fields models
    name = fields.Selection(
        [
         ('at_birth','At birth'),
         ('at_weaning','At weaning'),
         ('at_5_months','At 5 months')
        ],
        string="Time"
    )

    # Muestra del dia
    first_number_offspring = fields.Integer()
    second_number_offspring = fields.Integer()
    third_number_offspring = fields.Integer()

    # Muestras de litros de leche
    first_birth_weight = fields.Float(digits='Stock Weight')
    second_birth_weight = fields.Float(digits='Stock Weight')
    third_birth_weight = fields.Float(digits='Stock Weight')

    lot_id = fields.Many2one(
        'stock.lot'
    )