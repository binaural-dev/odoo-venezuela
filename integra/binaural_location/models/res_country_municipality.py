from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError


class ResCountryMunicipalityBinauralLocalizacion(models.Model):
    _name = "res.country.municipality"
    _rec_name = "name"
    _description = "Municipality"

    code = fields.Char(required=True)

    country_id = fields.Many2one("res.country", string="Country", required=True)

    state_id = fields.Many2many("res.country.state", string="State", required=True)

    name = fields.Char(string="Municipality", required=True)

    active = fields.Boolean(default=True)

    @api.onchange("name")
    def on_change_state(self):
        self.name = str(self.name or "").upper().strip()

    @api.constrains("country_id", "state_id", "name")
    def constraint_unique_municipality(self):
        for record in self:
            municipality = self.search(
                [
                    ("country_id", "=", record.country_id.id),
                    ("state_id", "=", record.state_id.id),
                    ("name", "=", record.name),
                    ("id", "!=", record.id),
                ]
            )

            if any(municipality):
                raise ValidationError(_("The municipality is already registered"))
