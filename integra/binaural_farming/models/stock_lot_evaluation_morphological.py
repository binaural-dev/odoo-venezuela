from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

class StockLotEvaluationMorphological(models.Model):
    _name = 'stock.lot.evaluation.morphological'
    _description = 'Evaluation morphological'

    
    # fields models
    types_morphological_id = fields.Many2one(
        'stock.lot.type.morphological',
        
    )
    types_qualitative_evaluation_id = fields.Many2one(
        'stock.lot.qualitative.valuation',
        
    )
    valuation_quantity = fields.Integer()

    # Relation to Stock Lot
    morphological_id = fields.Many2one(
        'stock.lot'
    )
                