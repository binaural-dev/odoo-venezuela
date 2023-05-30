# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies.

from odoo import models, api
import logging
_logger = logging.getLogger(__name__)


class ProductCatalogReport(models.AbstractModel):
    _inherit = 'report.sh_product_catalog_generator.product_catalog_doc'

    @api.model
    def _get_report_values(self, docids, data=None):
        default_data = super(ProductCatalogReport, self)._get_report_values(docids, data=data)

        default_data = {
            **default_data,
            'background': data['background'],
            'entry_page': data['entry_page'],
            'back_over': data['back_over'],
            'show_sales_policy': data['show_sales_policy'],
            'products_by_page': data['products_by_page'],
            'padding_top': data['padding_top'],
            'padding_sides': data['padding_sides'],
            'border_width': data['border_width'],
            'primary_color': data['primary_color'],
        }
        
        return default_data
        
        