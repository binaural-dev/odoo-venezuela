# -*- coding: utf-8 -*-
# Copyright (c) 2019-Present Droggol Infotech Private Limited. (<https://www.droggol.com/>)

from odoo import fields, models


class DrProductTags(models.Model):
    _name = 'dr.product.tags'
    _inherit = ['website.multi.mixin']
    _description = 'Product Tags'

    name = fields.Char(required=True, translate=True)
    product_ids = fields.Many2many('product.template', 'dr_product_tags_rel', 'tag_id', 'product_id', string='Products')
    product_count = fields.Integer(compute='_compute_product_count')
    active = fields.Boolean(default=True)


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    dr_tag_ids = fields.Many2many('dr.product.tags', 'dr_product_tags_rel', 'product_id', 'tag_id', string='Tags')
