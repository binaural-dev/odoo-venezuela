import json

from odoo import http
from odoo.addons.website_sale.controllers.main import WebsiteSale
from odoo.http import request


class WebsiteSaleBinauralSitioWeb(WebsiteSale):
    def _get_country_related_render_values(self, kw, render_values):
        '''
        This method provides fields related to the country to render the website sale form
        '''

        res = super()._get_country_related_render_values(kw, render_values)
        cities = request.env['res.country.city'].sudo().search([])
        res.update({"cities": cities})
        return res

    @http.route(['/shop/city_infos/<model("res.country.state"):state>'], type='http', auth="public", methods=['GET'], website=True)
    def city_infos(self, state, **kw):
        cities = request.env['res.country.city'].sudo().search_read([('state_id', '=', int(state))], ["id", "name"])
        return request.make_response(json.dumps(cities), [("Content-Type", "application/json")])
