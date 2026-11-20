from odoo import fields, models


class ResCountryParishBinauralLocalizacion(models.Model):
    _inherit = "res.partner"

    # The city is the one of Odoo (res.city, from base_address_extended), not a model of its own:
    # two definitions towards different tables break every update in between (R-49).
    city_id = fields.Many2one(string="City")

    # Plain text, as in the core and in 19: the name of res.city is translatable, and a related
    # field copies that, which would turn res_partner.city into a jsonb column.
    city = fields.Char(string="City related",
                       related="city_id.name", store=True, translate=False)

    municipality = fields.Many2one("res.country.municipality", "Municipality")

    parish_id = fields.Many2one(
        "res.country.parish", domain="[('municipality_id', '=', municipality)]"
    )

    zone_id = fields.Many2one("res.partner.zone", string="Zone")
