from odoo import fields, models


class ResCountryParishBinauralLocalizacion(models.Model):
    _inherit = "res.partner"

    city_id = fields.Many2one("res.country.city", string="City")

    city = fields.Char(string="City related", related="city_id.name", store=True)

    municipality = fields.Many2one("res.country.municipality", "Municipality")
