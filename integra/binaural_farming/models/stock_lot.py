from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import logging
_logger = logging.getLogger(__name__)

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

    # Relation into lots
    parent_father_id = fields.Many2one(
        'stock.lot', 
        'Parent Father Lots', 
        ondelete='cascade',
        domain="[('id','!=', id),('gender','=','male')]"
    )
    parent_mother_id = fields.Many2one(
        'stock.lot', 
        'Parent Mother Lots', 
        ondelete='cascade',
        domain="[('id','!=', id),('gender','=','female')]"
    )

    child_father_ids = fields.One2many(
        "stock.lot",
        "parent_father_id",
        string="Childs Father"
    )
    child_mother_ids = fields.One2many(
        "stock.lot",
        "parent_mother_id",
        string="Childs Mother"
    )
    
    names_parents = fields.Char(compute="_compute_names_parents", string="Names parents")
    names_parents_paternal = fields.Char(compute="_compute_names_parents_paternal", string="Names parents paternal")
    names_parents_maternal = fields.Char(compute="_compute_names_parents_maternal", string="Names parents maternal")

    amount_total_evaluation = fields.Integer(
        string='Amount total of evaluation',
        compute='_compute_amount_total_evaluation', 
        store=True,
    )

    final_quantification_id = fields.Many2one(
        "stock.lot.qualitative.valuation",
        string='Final quantification'
    )

    # Nuevos campos 
    production_types = fields.Selection(
        [
            ("dairy_breeds", "Dairy Breeds"),
            ("meat_breeds", "Meat Breeds")
        ],
        "Production Types",
        default="dairy_breeds",
    )

    publishing_on_the_web = fields.Boolean()

    # Cantidad de crias
    first_birth = fields.Integer()
    second_birth = fields.Integer()
    third_birth = fields.Integer()

    # Related to weight offspring
    lot_weight_offspring_ids = fields.One2many(
        'stock.lot.weight.offspring',
        'lot_id',
        string='Weight Offspring'
    )

    specie_id = fields.Many2one("stock.specie")
    
    # Computes
    # Parents lots
    @api.depends("name", "parent_father_id.names_parents", "parent_mother_id.names_parents")
    def _compute_names_parents(self):
        names = ""

        if self.parent_father_id: 
            names += f" (Padre) {self.parent_father_id.name}" 
        if self.parent_mother_id:
            names += f" (Madre) {self.parent_mother_id.name}"

        self.names_parents = names

    # Parents lots (Paternal)
    @api.depends("name", "parent_father_id.parent_father_id.names_parents_paternal")
    def _compute_names_parents_paternal(self):
        names = ""

        if self.parent_father_id.parent_father_id: 
            names += f" (Padre) {self.parent_father_id.parent_father_id.name}"
        if self.parent_father_id.parent_mother_id:
            names += f" (Madre) {self.parent_father_id.parent_mother_id.name}"

        self.names_parents_paternal = names

    # Parents lots (Maternal)
    @api.depends("name", "parent_mother_id.parent_mother_id.names_parents_maternal")
    def _compute_names_parents_maternal(self):
        names = ""

        if self.parent_mother_id.parent_father_id:
            names += f" (Padre) {self.parent_mother_id.parent_father_id.name}"
        if self.parent_mother_id.parent_mother_id:
            names += f" (Madre) {self.parent_mother_id.parent_mother_id.name}"

        self.names_parents_maternal = names

    @api.depends('lot_morphological_ids.valuation_quantity')
    def _compute_amount_total_evaluation(self):
        for lots in self:
            total = 0
            for qua_val in lots.lot_morphological_ids:
                total += qua_val.valuation_quantity
            
            lots.amount_total_evaluation = total

    @api.onchange("specie_id")
    def _onchange_specie(self):
        for lot in self:
            lot.lot_race_id = False