# -*- coding: utf-8 -*-
# from odoo import http


# class BinauralCostsMatrix(http.Controller):
#     @http.route('/binaural_costs_matrix/binaural_costs_matrix', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/binaural_costs_matrix/binaural_costs_matrix/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('binaural_costs_matrix.listing', {
#             'root': '/binaural_costs_matrix/binaural_costs_matrix',
#             'objects': http.request.env['binaural_costs_matrix.binaural_costs_matrix'].search([]),
#         })

#     @http.route('/binaural_costs_matrix/binaural_costs_matrix/objects/<model("binaural_costs_matrix.binaural_costs_matrix"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('binaural_costs_matrix.object', {
#             'object': obj
#         })
