from odoo import fields, models


class ResCountryParishBinauralLocalizacion(models.Model):
    _name = "res.country.parish"
    _description = "Parish"

    name = fields.Char(string="Name", required=True)

    code = fields.Char(string="Code", required=True)

    municipality_id = fields.Many2one(
        "res.country.municipality", string="Municipality", required=True
    )
