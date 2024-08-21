# Copyright (C) Softhealer Technologies.

from odoo import models, api, _
from odoo.http import request


class Product(models.Model):
    _inherit = 'product.product'

    @api.model
    def all_scan_search(self, barcode):
        product_id = self
        if barcode:
            if self.env.company.sh_search_char_field_product:
                state = True
                for char_fields in self.env.company.sh_search_char_field_product:
                    field_name = char_fields.name
                    field_value = barcode
                    if state:
                        product_id = self.search(
                            [(field_name, '=', field_value)], limit=1)
                        if product_id:
                            state = False
                        else:
                            state = True
                if product_id:
                    pricelists = self.env['product.pricelist'].sudo().search(
                        [('currency_id', '=', self.env.company.currency_id.id)], limit=1, order='id desc')
                    if pricelists:
                        list = True
                        price_list_value = 0.0
                        for pricelist in pricelists:
                            if list:
                                for item in pricelist.item_ids:
                                    if product_id.name == item.product_tmpl_id.name:
                                        price_list_value = item.fixed_price
                                        list = False
                    attribute_list = []
                    if product_id.product_template_attribute_value_ids:
                        for attribute in product_id.product_template_attribute_value_ids:
                            attribute_list.append(
                                str(attribute.product_attribute_value_id.name))
                    attribute_str = ''
                    attribute_str = ','.join(attribute_list)
                    msg_dict = {
                        'issuccess': 1, 'msg': _('Successfully Found Product corresponding to %(barcode)s') % {'barcode': barcode},
                    }
                    if price_list_value:
                        msg_dict.update({
                            'sh_product_pricelist': str(price_list_value),
                        })
                    if product_id.name:
                        msg_dict.update({
                            'sh_product_name': product_id.name,
                        })
                    if product_id.default_code:
                        msg_dict.update({
                            'sh_product_code': product_id.default_code,
                        })
                    if product_id.barcode:
                        msg_dict.update({
                            'sh_product_barcode': product_id.barcode,
                        })
                    if product_id.image_1920:
                        msg_dict.update({
                            'sh_product_image': product_id.image_1920,
                        })
                    if product_id.categ_id:
                        msg_dict.update({
                            'sh_product_category': product_id.categ_id.name,
                        })
                    if product_id.weight:
                        msg_dict.update({
                            'sh_product_weight': str(product_id.weight)+"  " + product_id.weight_uom_name,
                        })
                    if attribute_str != '':
                        msg_dict.update({
                            'sh_product_attribute': attribute_str,
                        })
                    else:
                        msg_dict.update({
                            'sh_product_attribute': '',
                        })
                    model_id = self.env['ir.model'].sudo().search(
                        [('model', '=', 'product.product')], limit=1)
                    currency_field_id = self.env['ir.model.fields'].sudo().search(
                        [('name', '=', 'currency_id'), ('model_id', '=', model_id.id)], limit=1)
                    list_price_field_id = self.env['ir.model.fields'].sudo().search(
                        [('name', '=', 'list_price'), ('model_id', '=', model_id.id)], limit=1)
                    qty_available_field_id = self.env['ir.model.fields'].sudo().search(
                        [('name', '=', 'qty_available'), ('model_id', '=', model_id.id)], limit=1)
                    uom_field_id = self.env['ir.model.fields'].sudo().search(
                        [('name', '=', 'uom_id'), ('model_id', '=', model_id.id)], limit=1)
                    description_sale_field_id = self.env['ir.model.fields'].sudo().search(
                        [('name', '=', 'description_sale'), ('model_id', '=', model_id.id)], limit=1)
                    if model_id:
                        if currency_field_id and list_price_field_id:
                            msg_dict.update({
                                'sh_product_sale_price': str(product_id.currency_id.symbol)+" "+str(product_id.list_price),
                            })
                        elif currency_field_id and not list_price_field_id:
                            msg_dict.update({
                                'sh_product_sale_price': str(product_id.currency_id.symbol)+" "+str('0.0'),
                            })
                        else:
                            msg_dict.update({
                                'sh_product_sale_price': str('0.0'),
                            })
                        if qty_available_field_id and uom_field_id:
                            msg_dict.update({
                                'sh_product_stock': str(product_id.qty_available) + ' '+str(product_id.uom_id.name),
                            })
                        elif not qty_available_field_id and uom_field_id:
                            msg_dict.update({
                                'sh_product_stock': str('0.0') + ' '+str(product_id.uom_id.name),
                            })
                        if qty_available_field_id and uom_field_id:
                            warehouse_list = []
                            cids = request and request.httprequest.cookies.get(
                                'cids')
                            if cids:
                                cids = [int(cid) for cid in cids.split(',')]
                            if cids and len(cids) > 1:
                                domain = [('company_id', 'in', cids)]
                            else:
                                domain = [
                                    ('company_id', '=', self.env.company.id)]

                            find_warehouse = self.env['stock.warehouse'].sudo().search(
                                domain)

                            for warehouse in find_warehouse:
                                warehouse_list.append({
                                    '%s' % (warehouse.name): str(product_id.with_context(warehouse=warehouse.id).virtual_available) + ' '+str(product_id.uom_id.name),
                                })
                            msg_dict.update({
                                'sh_product_stock': warehouse_list,
                            })
                        elif not qty_available_field_id and uom_field_id:
                            msg_dict.update({
                                'sh_product_stock': str('0.0') + ' '+str(product_id.uom_id.name),
                            })
                        if description_sale_field_id:
                            if product_id.description_sale:
                                msg_dict.update({
                                    'sh_product_sale_description': product_id.description_sale,
                                })
                            else:
                                msg_dict.update({
                                    'sh_product_sale_description': '',
                                })
                        else:
                            msg_dict.update({
                                'sh_product_sale_description': '',
                            })
                    return msg_dict
                else:
                    return {'msg': _('Not Found Corresponding to %(barcode)s') % {'barcode': barcode}}
            else:
                product_id = self.search([('barcode', '=', barcode)], limit=1)
                if product_id:
                    attribute_list = []
                    if product_id.product_template_attribute_value_ids:
                        for attribute in product_id.product_template_attribute_value_ids:
                            attribute_list.append(
                                str(attribute.product_attribute_value_id.name))
                    attribute_str = ''
                    attribute_str = ','.join(attribute_list)
                    msg_dict = {
                        'issuccess': 1, 'msg': _('Successfully Found Product corresponding to %(barcode)s') % {'barcode': barcode},
                    }
                    if product_id.name:
                        msg_dict.update({
                            'sh_product_name': product_id.name,
                        })
                    if product_id.default_code:
                        msg_dict.update({
                            'sh_product_code': product_id.default_code,
                        })
                    if product_id.barcode:
                        msg_dict.update({
                            'sh_product_barcode': product_id.barcode,
                        })
                    if product_id.image_1920:
                        msg_dict.update({
                            'sh_product_image': product_id.image_1920,
                        })
                    if product_id.categ_id:
                        msg_dict.update({
                            'sh_product_category': product_id.categ_id.name,
                        })
                    if product_id.weight:
                        msg_dict.update({
                            'sh_product_weight': product_id.weight,
                        })
                    if attribute_str != '':
                        msg_dict.update({
                            'sh_product_attribute': attribute_str,
                        })
                    else:
                        msg_dict.update({
                            'sh_product_attribute': '',
                        })
                    model_id = self.env['ir.model'].sudo().search(
                        [('model', '=', 'product.product')], limit=1)
                    currency_field_id = self.env['ir.model.fields'].sudo().search(
                        [('name', '=', 'currency_id'), ('model_id', '=', model_id.id)], limit=1)
                    list_price_field_id = self.env['ir.model.fields'].sudo().search(
                        [('name', '=', 'list_price'), ('model_id', '=', model_id.id)], limit=1)
                    qty_available_field_id = self.env['ir.model.fields'].sudo().search(
                        [('name', '=', 'qty_available'), ('model_id', '=', model_id.id)], limit=1)
                    uom_field_id = self.env['ir.model.fields'].sudo().search(
                        [('name', '=', 'uom_id'), ('model_id', '=', model_id.id)], limit=1)
                    description_sale_field_id = self.env['ir.model.fields'].sudo().search(
                        [('name', '=', 'description_sale'), ('model_id', '=', model_id.id)], limit=1)
                    if model_id:
                        if currency_field_id and list_price_field_id:
                            msg_dict.update({
                                'sh_product_sale_price': str(product_id.currency_id.symbol)+" "+str(product_id.list_price),
                            })
                        elif currency_field_id and not list_price_field_id:
                            msg_dict.update({
                                'sh_product_sale_price': str(product_id.currency_id.symbol)+" "+str('0.0'),
                            })
                        else:
                            msg_dict.update({
                                'sh_product_sale_price': str('0.0'),
                            })
                        if qty_available_field_id and uom_field_id:
                            msg_dict.update({
                                'sh_product_stock': str(product_id.qty_available) + ' '+str(product_id.uom_id.name),
                            })
                        elif not qty_available_field_id and uom_field_id:
                            msg_dict.update({
                                'sh_product_stock': str('0.0') + ' '+str(product_id.uom_id.name),
                            })
                        if description_sale_field_id:
                            if product_id.description_sale:
                                msg_dict.update({
                                    'sh_product_sale_description': product_id.description_sale,
                                })
                            else:
                                msg_dict.update({
                                    'sh_product_sale_description': '',
                                })
                        else:
                            msg_dict.update({
                                'sh_product_sale_description': '',
                            })
                    return msg_dict
                else:
                    return {'msg': _('Not Found Corresponding to %(barcode)s') % {'barcode': barcode}}
