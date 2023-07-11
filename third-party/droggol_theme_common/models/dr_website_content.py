# -*- coding: utf-8 -*-
# Copyright (c) 2019-Present Droggol Infotech Private Limited. (<https://www.droggol.com/>)

from odoo import fields, models
from odoo.tools.translate import html_translate


class DrWebsiteContent(models.Model):
    _name = 'dr.website.content'
    _description = 'Website Content'
    _inherit = 'dr.cache.mixin'
    _order = 'sequence,id'

    sequence = fields.Integer()
    name = fields.Char(required=True, translate=True)
    identifier = fields.Char('Extra Label', help="It is just displayed in backend dropdown and breadcrumb")
    description = fields.Char(translate=True)
    icon = fields.Char(default='list')
    content = fields.Html(sanitize_attributes=False, translate=html_translate, sanitize_form=False)
    content_type = fields.Selection([('tab', 'Product Tab'), ('offer_popup', 'Offer Popup'), ('attribute_popup', 'Attribute Popup')], default='tab', required=True, string='Type')

    dr_tab_products_ids = fields.Many2many('product.template', 'product_template_tab_rel', 'tab_id', 'product_template_id', string='Tab Products')
    dr_offer_products_ids = fields.Many2many('product.template', 'product_template_offer_rel', 'offer_id', 'product_template_id', string='Offer Products')

    def name_get(self):
        result = []
        for content in self:
            name = content.name
            if content.identifier:
                name = f'[{content.identifier}] {name}'
            result.append((content.id, name))
        return result

    def open_design_page(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'target': 'new',
            'url': '/droggol_theme_common/design_content/%s?enable_editor=1' % (self.id),
        }
