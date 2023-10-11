# -*- coding: utf-8 -*-

from odoo import api, fields, models, tools, _
from odoo.exceptions import ValidationError

#from odoo.addons.website.tools import get_video_embed_code


class MercadolibreProductImage(models.Model):
    _name = 'mercadolibre.product.image'
    _description = "MercadoLibre Product Image"
    _inherit = ['ocapi.product.image','mercadolibre.binding']

    conn_image_id = fields.Char(string="MercadoLibre Image Id",index=True)
    #product_tmpl_id = fields.Many2one('product.template', "Product Template", index=True, ondelete='cascade')
    binding_product_tmpl_id = fields.Many2one('mercadolibre.product_template', "Product Template", index=True, ondelete='cascade')
    #product_variant_id = fields.Many2one('product.product', "Product Variant", index=True, ondelete='cascade')
    binding_product_variant_id = fields.Many2one('mercadolibre.product', "Product Variant", index=True, ondelete='cascade')
