from odoo import api, fields, models


class ResCountryParishBinauralLocalizacion(models.Model):
    _inherit = "res.partner"

    city_id = fields.Many2one(
        "res.country.city",
        string="City",
        domain="[('country_id', '=?', country_id), ('state_id', '=?', state_id)]",
    )

    city = fields.Char(string="City related",
                       related="city_id.name", store=True)

    municipality = fields.Many2one("res.country.municipality", "Municipality")

    parish_id = fields.Many2one(
        "res.country.parish", domain="[('municipality_id', '=', municipality)]"
    )

    @api.onchange("state_id")
    def _onchange_state_id_clear_location(self):
        for partner in self:
            if partner.city_id and partner.city_id.state_id != partner.state_id:
                partner.city_id = False
            if partner.municipality and partner.state_id not in partner.municipality.state_id:
                partner.municipality = False
                partner.parish_id = False

    @api.onchange("municipality")
    def _onchange_municipality_clear_parish(self):
        for partner in self:
            if partner.parish_id and partner.parish_id.municipality_id != partner.municipality:
                partner.parish_id = False
