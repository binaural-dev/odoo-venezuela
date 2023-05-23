# -*- coding: utf-8 -*-
# Copyright (c) 2019-Present Droggol Infotech Private Limited. (<https://www.droggol.com/>)

from PIL import ImageColor
from odoo import api, fields, models


class DrProductLabel(models.Model):
    _name = 'dr.product.label'
    _description = 'Product Label'
    _inherit = 'dr.cache.mixin'

    name = fields.Char(required=True, translate=True)
    background_color = fields.Char('Background Color', default='#000000')
    background_color_rgb = fields.Char(compute='_compute_background_color_rgb', store=True, string='Background Color RGB')
    text_color = fields.Char('Text Color', default='#FFFFFF')
    style = fields.Selection([('1', 'Tag'), ('2', 'Badge'), ('3', 'Circle'), ('4', 'Square')], default='1', required=True)
    product_count = fields.Integer(compute='_compute_product_count')
    active = fields.Boolean(default=True)

    def _compute_product_count(self):
        label_data = self.env['product.template'].read_group([('dr_label_id', 'in', self.ids)], ['dr_label_id'], ['dr_label_id'])
        mapped_data = dict([(x['dr_label_id'][0], x['dr_label_id_count']) for x in label_data])
        for label in self:
            label.product_count = mapped_data.get(label.id, 0)

    @api.depends('background_color')
    def _compute_background_color_rgb(self):
        for label in self:
            colors = ImageColor.getcolor(label.background_color, 'RGB')
            label.background_color_rgb = '%s, %s, %s' % (colors[0], colors[1], colors[2])

    def action_open_products(self):
        self.ensure_one()
        action = self.env.ref('website_sale.product_template_action_website').read()[0]
        action['domain'] = [('dr_label_id', '=', self.id)]
        action['context'] = {}
        return action
