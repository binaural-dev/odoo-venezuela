# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies.

from odoo import models, api
from odoo.tools import float_round
from odoo.tools.misc import formatLang
import numpy as np
import logging
_logger = logging.getLogger(__name__)


class ProductCatalogReport(models.AbstractModel):
    _inherit = 'report.sh_product_catalog_generator.product_catalog_doc'


    def _get_final_product_list(self, final_product_dic):
        final_product_list = [final_product_dic[product] for product in final_product_dic.keys()]
        
        return final_product_list[0] if len(final_product_list) > 0 else final_product_dic
        
    @api.model
    def _prepare_product_dict(self, record, price, data, currency_id):
        def get_price(self, price):
            if data.get("price_without_tax"):
                return self.product_tmpl_id.taxes_id.compute_all(price, currency_id, 1)["total_excluded"]
            else:
                return self.product_tmpl_id.taxes_id.compute_all(price, currency_id, 1)["total_included"]

        price = float_round(price, precision_digits=currency_id.decimal_places)
        return {
            "id": record.id,
            "default_code": record.default_code,
            "name": record.name,
            "cat_name": record.categ_id.name,
            "image": record.image_1920,
            "price": formatLang(self.env, get_price(record, price), currency_obj=currency_id, digits=currency_id.decimal_places),
            "description": record.description_sale,
            "template_id": record.product_tmpl_id.id,
            "currency_id": currency_id.symbol,
            "uom": record.uom_id.name,
            "quantity": record.quantity,
            "list_price": formatLang(self.env, record.list_price , currency_obj=currency_id, digits=currency_id.decimal_places)
        }

    @api.model
    def _get_catalog_report_values(self, docids, data=None):
        """Prepared catalog report dynamic values
            data params used for get dynamic data based on configuration from catalog popup
        """
        product_obj = self.env["product.product"]
        final_product_dic = {}
        product_dict_list = []
        row_list = []
        count = 0
        currency_id = self.env['res.currency'].sudo().browse(
            data.get('currency_id')[0])
        if data.get('catalog_type') == 'product':
            if data.get('product_ids'):
                total_product = len(data.get('product_ids'))
                for product in data.get('product_ids'):
                    domain = [("id", "=", product)]
                    search_products = product_obj.search(domain)
                    
                    for search_product in search_products:
                        if search_product:
                            price = 0.0
                            if data.get('pricelist_id'):
                                pricelist_id = self.env['product.pricelist'].sudo().browse(
                                    data.get('pricelist_id')[0])
                                price = pricelist_id._get_product_price(
                                    search_product, 1.0)
                            else:
                                price = search_product.list_price
                            product_dic = self._prepare_product_dict(search_product, price, data, currency_id) 
                            product_dict_list.append(product_dic)
                            count = count + 1
                            total_product = total_product - 1
                            if data.get('style') == 'style_2' or data.get('style') == 'style_5':
                                if int(data.get('style_box')) == 2:
                                    if count == 2 or total_product == 0:
                                        count = 0
                                        row_list.append(product_dict_list)
                                        product_dict_list = []
                                elif int(data.get('style_box')) == 3:
                                    if count == 3 or total_product == 0:
                                        count = 0
                                        row_list.append(product_dict_list)
                                        product_dict_list = []
                                if int(data.get('style_box')) == 4:
                                    if count == 4 or total_product == 0:
                                        count = 0
                                        row_list.append(product_dict_list)
                                        product_dict_list = []

                            elif data.get('style') == 'style_4':
                                if count == 2 or total_product == 0:
                                    count = 0
                                    row_list.append(product_dict_list)
                                    product_dict_list = []
        elif data.get('catalog_type') == 'category':
            if data.get('category_ids'):
                for category in data.get("category_ids"):
                    product_list = []
                    row_list = []
                    domain = [("categ_id", "=", category)]
                    search_products = product_obj.search(domain)
                    total_product = len(search_products.ids)

                    if search_products:
                        for rec in search_products:
                            price = 0.0
                            if data.get('pricelist_id'):
                                pricelist_id = self.env['product.pricelist'].sudo().browse(
                                    data.get('pricelist_id')[0])
                                price = pricelist_id._get_product_price(
                                    rec, 1.0)
                            else:
                                price = rec.list_price
                            product_dic = self._prepare_product_dict(rec, price, data, currency_id) 
                            product_list.append(product_dic)
                            count = count + 1
                            total_product = total_product - 1
                            if data.get('style') == 'style_2' or data.get('style') == 'style_5':
                                if int(data.get('style_box')) == 2:
                                    if count == 2 or total_product == 0:
                                        count = 0
                                        row_list.append(product_list)
                                        product_list = []
                                elif int(data.get('style_box')) == 3:
                                    if count == 3 or total_product == 0:
                                        count = 0
                                        row_list.append(product_list)
                                        product_list = []
                                if int(data.get('style_box')) == 4:
                                    if count == 4 or total_product == 0:
                                        count = 0
                                        row_list.append(product_list)
                                        product_list = []
                            elif data.get('style') == 'style_4':
                                if count == 2 or total_product == 0:
                                    count = 0
                                    row_list.append(product_list)
                                    product_list = []
                    search_category = self.env['product.category'].search([
                        ('id', '=', category)
                    ], limit=1)
                    if search_category and data.get('style') == 'style_2' or data.get('style') == 'style_5' or data.get('style') == 'style_4':
                        final_product_dic.update(
                            {search_category.name: row_list})
                    else:
                        final_product_dic.update(
                            {search_category.name: product_list})

        if data.get("order_by_name", False):
            product_dict_list = list(sorted(product_dict_list, key=lambda x: x["name"]))
        data = {
            'catalog_type': data['catalog_type'],
            'price': data['price'],
            'image': data['image'],
            'image_size': data['image_size'],
            'description': data['description'],
            'product_link': data['product_link'],
            'style': data['style'],
            'row_list': row_list,
            'int_ref': data['int_ref'],
            'product_dict_list': product_dict_list,
            'final_product_dic': final_product_dic,
            'style_box': data['style_box'],
            'break_page': data['break_page'],
            'break_page_after_products': data['break_page_after_products'],
            'name': data['name'],
            'sh_add_uom_catalog': data['sh_add_uom_catalog'],
            'sh_print_category_name': data['sh_print_category_name'],
            'final_product_list': self._get_final_product_list(final_product_dic),
        }
        return data

        
    @api.model
    def _get_report_values(self, docids, data=None):
        default_data = self._get_catalog_report_values(docids, data)

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
            'show_available_qty': data['show_available_qty'],
            'price_without_tax': data['price_without_tax']

        }
        
        return default_data
        
        
