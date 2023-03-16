# -*- coding: utf-8 -*-

# from odoo import models, fields, api


# class binaural_stock(models.Model):
#     _name = 'binaural_stock.binaural_stock'
#     _description = 'binaural_stock.binaural_stock'

#     name = fields.Char()
#     value = fields.Integer()
#     value2 = fields.Float(compute="_value_pc", store=True)
#     description = fields.Text()
#
#     @api.depends('value')
#     def _value_pc(self):
#         for record in self:
#             record.value2 = float(record.value) / 100
