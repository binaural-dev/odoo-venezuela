# -*- coding: utf-8 -*-
# from odoo import http


# class BinauralFilterPartnerMixin(http.Controller):
#     @http.route('/binaural_filter_partner_mixin/binaural_filter_partner_mixin', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/binaural_filter_partner_mixin/binaural_filter_partner_mixin/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('binaural_filter_partner_mixin.listing', {
#             'root': '/binaural_filter_partner_mixin/binaural_filter_partner_mixin',
#             'objects': http.request.env['binaural_filter_partner_mixin.binaural_filter_partner_mixin'].search([]),
#         })

#     @http.route('/binaural_filter_partner_mixin/binaural_filter_partner_mixin/objects/<model("binaural_filter_partner_mixin.binaural_filter_partner_mixin"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('binaural_filter_partner_mixin.object', {
#             'object': obj
#         })
