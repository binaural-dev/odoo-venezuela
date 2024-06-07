from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

class StockLot(models.Model):
    _inherit = "stock.lot"

    # fields models
    image = fields.Image()
    gender = fields.Selection(
        [
            ("male", "Male"),
            ("female", "Female")
        ],
        "Gender",
        default="",
    )
    name_lot = fields.Char()
    tatto_left = fields.Char()
    tatto_right = fields.Char()
    adga_registration_number = fields.Char()
    asoembra_registration_number = fields.Char()
    date_of_birth  = fields.Date()
    
    # Related to race
    lot_race_id = fields.Many2one(
        "stock.lot.race",
        default=lambda self: self.lot_race_id,
        domain=[("active", "=", True)],
    )

    # Relation to owner
    res_partner_owner_id = fields.Many2one(
        'res.partner',
        domain=[("is_owner", "=", True)],
        default=lambda self: self.res_partner_owner_id.display_name
    )
    # fields to owner
    proprietary_acronym = fields.Char(
        related="res_partner_owner_id.proprietary_acronym"
    )
    
    # Relation to breeder
    lot_breeder_ids = fields.Many2one(
        'stock.lot.breeder', 
        ondelete="cascade",
        domain=[("active", "=", True)],
    )

    # Related to ancestrys
    lot_ancestry_ids = fields.One2many(
        'stock.lot.ancestral.milk.production',
        'lot_id',
        string='Ancestral milk production'
    )

    # Relation to types morphological
    lot_morphological_ids = fields.One2many(
        'stock.lot.evaluation.morphological',
        'morphological_id',
        string='Evaluation Morphological'
    )