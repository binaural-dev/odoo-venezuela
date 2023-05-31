# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies.

from odoo import models, fields, api
import base64
from PyPDF2 import PdfFileWriter, PdfFileReader
import io
import logging
_logger = logging.getLogger(__name__)

class GenerateProductCatalogWizard(models.TransientModel):
    _inherit = 'product.catalog.wizard'
    _description = 'Product Catalog Wizard'

    style = fields.Selection(
        [
            ('style_1', 'Style 1'),
            ('style_2', 'Style 2'),
            ('style_3', 'Style 3'),
            ('style_4', 'Style 4'), 
            ('style_5', 'Style 5'),
            ('style_6', 'Style 6')
        ], 
        default='style_1',
        string='Style'
    )
    image = fields.Boolean(string='Image', default=True)
    product_ids = fields.Many2many('product.product', string='Products', default=lambda self: self.env.context.get('active_ids', []))
    background = fields.Binary(string="Background", default=lambda self: self.env.company.background)
    entry_page = fields.Binary(string="Entry Page", default=lambda self: self.env.company.entry_page)
    back_over = fields.Binary(string="Back Over", default=lambda self: self.env.company.back_over)

    show_available_qty = fields.Boolean(string="Show Available Qty")
    show_sales_policy = fields.Boolean(string="Show Sales Policy")
    products_by_page = fields.Integer('Products by page', default=lambda self: self.env.company.products_by_page)
    padding_top = fields.Float('Margin top', default=lambda self: self.env.company.padding_top)
    padding_sides = fields.Float('Margin sides', default=lambda self: self.env.company.padding_sides)
    border_width = fields.Integer('Border width', default=lambda self: self.env.company.border_width)
    primary_color = fields.Char('Primary color', default=lambda self: self.env.company.primary_color)


    def print_report(self):
        return super(GenerateProductCatalogWizard,self).print_report()
