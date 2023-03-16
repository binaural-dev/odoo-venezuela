# -*- coding: utf-8 -*-
# from odoo import http


# class BinauralStock(http.Controller):
#     @http.route('/binaural_stock/binaural_stock', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/binaural_stock/binaural_stock/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('binaural_stock.listing', {
#             'root': '/binaural_stock/binaural_stock',
#             'objects': http.request.env['binaural_stock.binaural_stock'].search([]),
#         })

#     @http.route('/binaural_stock/binaural_stock/objects/<model("binaural_stock.binaural_stock"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('binaural_stock.object', {
#             'object': obj
#         })
