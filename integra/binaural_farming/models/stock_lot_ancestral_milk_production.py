from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

class StockLotAncestralMilkProduction(models.Model):
    _name = 'stock.lot.ancestral.milk.production'
    
    # fields models
    name = fields.Char()
    ancestry = fields.Char()
    first_day_liters = fields.Float(digits='Stock Weight')
    second_day_liters = fields.Float(digits='Stock Weight')
    third_day_liters = fields.Float(digits='Stock Weight')

    lot_id = fields.Many2one(
        'stock.lot'
    )

    # Datos de producción de leche de ancestros
    # Filas (Madre, Abuela Paterna, Abuela Materna)
    # Columnas (LT Días, LT Días, LT Días)
    # Mother 
    # Paternal Grandmother
    # Maternal Grandmother