# -*- coding: utf-8 -*-
# Copyright (c) 2019-Present Droggol Infotech Private Limited. (<https://www.droggol.com/>)

from odoo import fields, models


class DrProductPublicCategoryLabel(models.Model):
    _name = 'dr.product.public.category.label'
    _description = 'Category Label'

    name = fields.Char(required=True, translate=True)
    background_color = fields.Char('Background Color', default='#000000')
    text_color = fields.Char('Text Color', default='#FFFFFF')
