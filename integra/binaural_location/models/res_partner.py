from odoo import fields, models


class ResCountryParishBinauralLocalizacion(models.Model):
    _inherit = "res.partner"

    city_id = fields.Many2one("res.country.city", string="City")
