from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

class StockLotRace(models.Model):
    _name = 'stock.lot.race'
    _description = 'Manage race'
    _rec_name = 'description'

    # fields models
    description = fields.Char()
    active = fields.Boolean(default=True)
    specie_id = fields.Many2one("stock.specie")

    def unlink(self):
        lot_ids = self.env["stock.lot"].search([("lot_race_id","=", self.id)])
        if lot_ids:
            raise ValidationError(_("You cannot delete this record since it is used in Stock Lot"))
        return super().unlink()