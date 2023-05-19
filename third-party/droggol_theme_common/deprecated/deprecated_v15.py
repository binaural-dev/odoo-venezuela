# -*- coding: utf-8 -*-
# Copyright (c) 2019-Present Droggol Infotech Private Limited. (<https://www.droggol.com/>)

from odoo import fields, models
from odoo.tools.translate import html_translate


class DrProductBrand(models.Model):
    _name = 'dr.product.brand'
    _inherit = ['website.multi.mixin']
    _description = 'Product Brand'
    _order = 'sequence,id'

    name = fields.Char(required=True, translate=True)
    description = fields.Char(translate=True)
    image = fields.Binary()
    sequence = fields.Integer(string='Sequence')
    active = fields.Boolean(default=True)


class DrProductOffer(models.Model):
    _name = 'dr.product.offer'
    _description = 'Product Offers'
    _order = 'sequence,id'

    name = fields.Char(string='Title', required=True, translate=True)
    description = fields.Char(string='Description', required=True, translate=True)
    icon = fields.Char(default='list')
    sequence = fields.Integer(string='Sequence')
    dialog_content = fields.Html(sanitize_attributes=False, translate=html_translate, sanitize_form=False)
    product_id = fields.Many2one('product.template')
    tag_id = fields.Many2one('dr.product.tags')


class DrProductTabs(models.Model):
    _name = 'dr.product.tabs'
    _description = 'Product Tabs'
    _order = 'sequence,id'

    name = fields.Char(string='Title', required=True, translate=True)
    icon = fields.Char(default='list')
    content = fields.Html(sanitize_attributes=False, translate=html_translate, sanitize_form=False)
    sequence = fields.Integer(string='Sequence')
    product_id = fields.Many2one('product.template')
    tag_id = fields.Many2one('dr.product.tags')


class DrProductTagsExt(models.Model):
    _inherit = 'dr.product.tags'

    dr_tab_ids = fields.One2many('dr.product.tabs', 'tag_id', string='Tabs', help='Display in product detail page on website.')
    dr_offer_ids = fields.One2many('dr.product.offer', 'tag_id', string='Offers', help='Display in product detail page on website.')


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    dr_brand_id = fields.Many2one('dr.product.brand')
    dr_offer_ids = fields.One2many('dr.product.offer', 'product_id', help='Display in product detail page on website.')
    dr_tab_ids = fields.One2many('dr.product.tabs', 'product_id', help='Display in product detail page on website.')


class WebsiteMenu(models.Model):
    _inherit = 'website.menu'

    dr_is_special_menu = fields.Boolean()
