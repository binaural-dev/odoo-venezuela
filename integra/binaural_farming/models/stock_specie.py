from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

class StockSpecie(models.Model):
    _name = 'stock.specie'
    _description = 'Animal Species'

    _sql_constraints = [
        (
            "name_unique",
            "unique(name)",
            _("The name must be unique"),
        ),
    ]
    
    # fields models
    name = fields.Char(required=True, string="Specie name")

    def write(self, vals):
        raise ValidationError(_("You cannot edit this record"))

    def unlink(self):
        race_ids = self.env["stock.lot.race"].search([("specie_id","=", self.id)])
        if race_ids:
            raise ValidationError(_("You cannot delete this record since it is used in Races"))
        return super().unlink()