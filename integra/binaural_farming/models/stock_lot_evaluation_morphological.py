from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

class StockLotEvaluationMorphological(models.Model):
    _name = 'stock.lot.evaluation.morphological'

    
    # fields models
    name = fields.Char()

    types_morphological_id = fields.Many2one(
        'stock.lot.type.morphological'
    )
    types_qualitative_evaluation_id = fields.Many2one(
        'stock.lot.qualitative.valuation'
    )

    valuation_quantity = fields.Integer()
    
    morphological_id = fields.Many2one(
        'stock.lot'
    )