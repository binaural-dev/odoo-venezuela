from odoo import fields, models


class ResCountryCityBinauralLocalizacion(models.Model):
    _name = "res.country.city"
    _rec_name = "name"
    _description = "City"
    _sql_constraints = [
        (
            "name_uniq",
            "unique (name,country_id,state_id)",
            "You cannot register a city with the same name for the selected state and country",
        )
    ]

    country_id = fields.Many2one("res.country", string="Country", required=True)

    state_id = fields.Many2one("res.country.state", string="State", required=True)

    name = fields.Char(string="City", required=True)
