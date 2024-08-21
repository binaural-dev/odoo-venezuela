# Copyright (C) Softhealer Technologies.

from odoo import models, api


class ProductCatalogReport(models.AbstractModel):
    _name = 'report.sh_product_catalog_generator.product_catalog_doc'
    _description = "product catalog report abstract model"

    @api.model
    def _get_report_values(self, docids, data=None):

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
                    if search_products:
                        price = 0.0
                        if data.get('pricelist_id'):
                            pricelist_id = self.env['product.pricelist'].sudo().browse(
                                data.get('pricelist_id')[0])
                            price = pricelist_id._get_product_price(
                                search_products, 1.0)
                        else:
                            price = search_products.list_price
                        product_dic = {
                            'id': search_products.id,
                            'default_code': search_products.default_code,
                            'name': search_products.name_get()[0][1],
                            'cat_name': search_products.categ_id.name,
                            'image': search_products.image_1920,
                            'price': format(price, '.'+str(data['sh_price_decimal_places'])+"f"),
                            'description': search_products.description_sale,
                            'template_id': search_products.product_tmpl_id.id,
                            'currency_id': currency_id.symbol,
                            'uom': search_products.uom_id.name,
                        }
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
                for category in data.get('category_ids'):
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
                            product_dic = {
                                'default_code': rec.default_code,
                                'name': rec.name_get()[0][1],
                                'cat_name': rec.categ_id.name,
                                'image': rec.image_1920,
                                'price': format(price, '.'+str(data['sh_price_decimal_places'])+"f"),
                                'description': rec.description_sale or '',
                                'template_id': rec.product_tmpl_id.id,
                                'currency_id': currency_id.symbol,
                                'id': rec.id,
                                'uom': rec.uom_id.name,
                            }
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
            'sh_print_category_name': data['sh_print_category_name']
        }
        return data
