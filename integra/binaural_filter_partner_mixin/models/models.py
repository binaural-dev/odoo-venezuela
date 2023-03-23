# -*- coding: utf-8 -*-

# from odoo import models, fields, api


# class binaural_filter_partner_mixin(models.Model):
#     _name = 'binaural_filter_partner_mixin.binaural_filter_partner_mixin'
#     _description = 'binaural_filter_partner_mixin.binaural_filter_partner_mixin'

#     name = fields.Char()
#     value = fields.Integer()
#     value2 = fields.Float(compute="_value_pc", store=True)
#     description = fields.Text()
#
#     @api.depends('value')
#     def _value_pc(self):
#         for record in self:
#             record.value2 = float(record.value) / 100
