from odoo import _, http
from odoo.http import request
from odoo.osv import expression
from odoo.addons.website_sale.controllers.main import WebsiteSale
import logging

_logger = logging.getLogger(__name__)

class WebsiteSale(WebsiteSale):

    @http.route(['/shop/cart'], type='http', auth="public", website=True, sitemap=False)
    def cart(self, access_token=None, revive='', **post):
        res = super().cart(access_token, revive, **post)
        if request.env.user.employee_id.is_seller:
            return request.redirect('/shop')
    
        return res

    
    def _get_search_domain(self, search, category, attrib_values, search_in_description=True):
        res = super()._get_search_domain(search, category, attrib_values, search_in_description)
        if request.env.user.employee_id.is_seller:
            res = expression.AND([res, [('detailed_type', '=', "product")]])
        return res
    

    def _shop_lookup_products(self, attrib_set, options, post, search, website):
        res = super()._shop_lookup_products(attrib_set, options, post, search, website)
        if request.env.user.employee_id.is_seller:
            products = res[2]
            products = products.filtered(lambda p: p.detailed_type == "product")
            res = (res[0], res[1], products)
        return res