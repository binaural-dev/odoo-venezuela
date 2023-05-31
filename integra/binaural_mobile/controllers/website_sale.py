from odoo import _, http
from odoo.http import request
from odoo.osv import expression
from odoo.addons.website_sale.controllers.main import WebsiteSale
from odoo.addons.website.models.ir_http import sitemap_qs2dom
import logging

_logger = logging.getLogger(__name__)

class WebsiteSale(WebsiteSale):
    def sitemap_shop(env, rule, qs):
        if not qs or qs.lower() in '/shop':
            yield {'loc': '/shop'}

        Category = env['product.public.category']
        dom = sitemap_qs2dom(qs, '/shop/category', Category._rec_name)
        dom += env['website'].get_current_website().website_domain()
        for cat in Category.search(dom):
            loc = '/shop/category/%s' % slug(cat)
            if not qs or qs.lower() in loc:
                yield {'loc': loc}

    @http.route(['/shop/cart'], type='http', auth="public", website=True, sitemap=False)
    def cart(self, access_token=None, revive='', **post):
        res = super().cart(access_token, revive, **post)
        if request.env.user.employee_id.is_seller:
            return request.redirect('/shop')
        
        return res

    @http.route([
        '/shop',
        '/shop/page/<int:page>',
        '/shop/category/<model("product.public.category"):category>',
        '/shop/category/<model("product.public.category"):category>/page/<int:page>',
    ], type='http', auth="public", website=True, sitemap=sitemap_shop)
    def shop(self, page=0, category=None, search='', min_price=0.0, max_price=0.0, ppg=False, **post):
        res = super().shop(page, category, search, min_price, max_price, ppg, **post)
        
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