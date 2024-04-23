# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

import base64
import hashlib
import json
import logging
import time
from builtins import int
from datetime import datetime
import requests
from dateutil import parser
import pytz

from odoo import models, fields, api
from .. import shopify
from ..shopify.pyactiveresource.connection import ClientError

utc = pytz.utc
_logger = logging.getLogger("Shopify Template")


class ProductCategory(models.Model):
    """
    Inherited model for managing the shopify categories.
    """
    _inherit = "product.category"
    is_shopify_product_cat = fields.Boolean(string="Shopify Product Category?", default=False,
                                            help="This is used for an identity for is Shopify category or odoo "
                                                 "category.if is True it means is Shopify category")


class ShopifyProductTemplateEpt(models.Model):
    _name = "shopify.product.template.ept"
    _description = "Shopify Product Template"

    name = fields.Char(translate=True)
    shopify_instance_id = fields.Many2one("shopify.instance.ept", "Instance")
    product_tmpl_id = fields.Many2one("product.template", "Product Template")
    shopify_tmpl_id = fields.Char("Shopify Template Id")
    exported_in_shopify = fields.Boolean(default=False)
    shopify_product_ids = fields.One2many("shopify.product.product.ept", "shopify_template_id",
                                          "Products")
    template_suffix = fields.Char()
    created_at = fields.Datetime()
    updated_at = fields.Datetime()
    published_at = fields.Datetime()
    website_published = fields.Selection([('unpublished', 'Unpublished'), ('published_web', 'Published in Web Only'),
                                          ('published_global', 'Published in Web and POS')],
                                         default='unpublished', copy=False, string="Published ?")
    tag_ids = fields.Many2many("shopify.tags", "shopify_tags_rel", "product_tmpl_id", "tag_id",
                               "Tags")
    description = fields.Html(translate=True)
    total_variants_in_shopify = fields.Integer("Total Variants", default=0)
    total_sync_variants = fields.Integer("Total Synced Variants", compute="_compute_total_sync_variants",
                                         store=True)
    shopify_product_category = fields.Many2one("product.category", "Product Category")
    active = fields.Boolean(default=True)
    shopify_image_ids = fields.One2many("shopify.product.image.ept", "shopify_template_id")

    @api.depends("shopify_product_ids.exported_in_shopify", "shopify_product_ids.variant_id")
    def _compute_total_sync_variants(self):
        """ This method used to compute the total sync variants.
            @param : self,import_data_id,common_log_obj
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 07/10/2019.
        """
        for template in self:
            variants = template.shopify_product_ids.filtered(lambda x: x.exported_in_shopify and x.variant_id)
            template.total_sync_variants = variants and len(variants) or 0

    def write(self, vals):
        """
        This method use to archive/unarchive shopify product variants base on shopify product templates.
        @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 09/12/2019.
        :Task id: 158502
        """
        shopify_product_product_obj = self.env["shopify.product.product.ept"]
        if "active" in vals.keys():
            for shopify_template in self:
                shopify_template.shopify_product_ids.write({"active": vals.get("active")})
                if vals.get("active"):
                    shopify_variants = shopify_product_product_obj.search(
                        [("shopify_template_id", "=", shopify_template.id),
                         ("shopify_instance_id", "=",
                          shopify_template.shopify_instance_id.id),
                         ("active", "=", False)])
                    shopify_variants.write({"active": vals.get("active")})
        res = super(ShopifyProductTemplateEpt, self).write(vals)
        return res

    @api.model
    def find_template_attribute_values(self, template_options, product_template_id, variant):
        """
        This method is used for create domain for the template attribute value from the
        product.template.attribute.value
        Author : Bhavesh Jadav 12/12/2019
        template_options: Attributes for searching by name in odoo.
        product_template_id: use for the odoo product template.
        variant: use for the product variant response from the shopify datatype should be dict
        return: template_attribute_value_domain data type list
        @change: Maulik Barad on Date 04-Sep-2020.
        """
        product_attribute_obj = self.env["product.attribute"]

        product_attribute_list = []

        for attribute in template_options:
            product_attribute = product_attribute_obj.get_attribute(attribute.get("name"), auto_create=True)[0]
            product_attribute_list.append(product_attribute.id)

        template_attribute_value_domain = self.prepare_template_attribute_value_domain(product_attribute_list, variant,
                                                                                       product_template_id)

        if len(product_attribute_list) != len(template_attribute_value_domain):
            return []

        return template_attribute_value_domain

    def prepare_template_attribute_value_domain(self, product_attribute_list, variant, product_template_id):
        """ This method is used to prepare template attribute value domain.
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 21 October 2020 .
            Task_id: 167537
        """
        template_attribute_value_domain = []
        product_attribute_value_obj = self.env["product.attribute.value"]
        product_template_attribute_value_obj = self.env["product.template.attribute.value"]
        counter = 0
        for product_attribute in product_attribute_list:
            counter += 1
            attribute_name = "option" + str(counter)
            attribute_val = variant.get(attribute_name)
            product_attribute_value = product_attribute_value_obj.get_attribute_values(attribute_val, product_attribute,
                                                                                       auto_create=True)

            if product_attribute_value:
                product_attribute_value = product_attribute_value[0]
                template_attribute_value_id = product_template_attribute_value_obj.search(
                    [("product_attribute_value_id", "=", product_attribute_value.id),
                     ("attribute_id", "=", product_attribute),
                     ("product_tmpl_id", "=", product_template_id)], limit=1)
                if template_attribute_value_id:
                    domain = ("product_template_attribute_value_ids", "=", template_attribute_value_id.id)
                    template_attribute_value_domain.append(domain)

        return template_attribute_value_domain

    def shopify_create_simple_product(self, product_name, variant_data, description, attribute_line_data=[]):
        """
        This method is used to create simple product having no variants.
        @author: Maulik Barad on Date 07-Sep-2020.
        """
        odoo_product = self.env["product.product"]
        detailed_type = 'product'

        if not variant_data.get('requires_shipping'):
            detailed_type = 'service'

        sku = variant_data.get("sku", "")
        barcode = variant_data.get("barcode")

        if sku or barcode:
            vals = {"name": product_name,
                    "detailed_type": detailed_type,
                    "default_code": sku}

            if self.env["ir.config_parameter"].sudo().get_param("shopify_ept.set_sales_description"):
                vals.update({"description_sale": description})

            if barcode:
                vals.update({"barcode": barcode})

            odoo_product = odoo_product.create(vals)
            if attribute_line_data:
                odoo_product.product_tmpl_id.write({"attribute_line_ids": attribute_line_data})

        return odoo_product

    def import_product_for_order(self, template_id, order_queue_line, model_name, instance):
        """
        Get data of a product for creating it while it processing from order process.
        @param template_id: Shopify Template id.
        @param order_queue_line: Order Queue Line.
        @param model_id: Id of model.
        @author: Maulik Barad on Date 01-Sep-2020.
        """
        result = False
        try:
            result = [shopify.Product().find(template_id)]
        except ClientError as error:
            if hasattr(error, "response"):
                if error.response.code == 429 and error.response.msg == "Too Many Requests":
                    time.sleep(int(float(error.response.headers.get('Retry-After', 5))))
                    result = [shopify.Product().find(template_id)]
                    return result
                message = "Error while importing product for order. Product ID: %s.\nError: %s\n%s" % (
                    template_id, str(error.response.code) + " " + error.response.msg,
                    json.loads(error.response.body.decode()).get("errors")[0])
                self.create_log_line_for_queue_line(instance, message, model_name, False, order_queue_line, "")
        except Exception as error:
            if order_queue_line:
                message = "Shopify product did not exist in Shopify store with product id: %s \nError : %s" % (
                    template_id, str(error))
                self.create_log_line_for_queue_line(instance, message, model_name, False, order_queue_line, "")

        return result

    def prepare_variant_vals(self, instance, variant_data):
        """
        This method used to prepare a shopify variant dictionary.
        @param instance:
        @param variant_data: Data of Shopify variant.
        @author: Maulik Barad on Date 01-Sep-2020.
        """
        variant_vals = {"shopify_instance_id": instance.id,
                        "variant_id": variant_data.get("id"),
                        "sequence": variant_data.get("position"),
                        "default_code": variant_data.get("sku", ""),
                        "inventory_item_id": variant_data.get("inventory_item_id"),
                        "inventory_management": "shopify" if variant_data.get(
                            "inventory_management") == "shopify" else "Dont track Inventory",
                        "check_product_stock": variant_data.get("inventory_policy"),
                        "taxable": variant_data.get("taxable"),
                        "created_at": self.convert_shopify_date_into_odoo_format(variant_data.get("created_at")),
                        "updated_at": self.convert_shopify_date_into_odoo_format(variant_data.get("updated_at")),
                        "exported_in_shopify": True,
                        "active": True}

        return variant_vals

    def create_log_line_for_queue_line(self, instance, message, model_name, product_data_line_id, order_data_line_id,
                                       product_sku, create_activity=False):
        """
        Creates log line as per queue line provided.
        @author: Maulik Barad on Date 03-Sep-2020.
        """
        common_log_line_obj = self.env["common.log.lines.ept"]
        shopify_product_queue_obj = self.env["shopify.product.data.queue.ept"]
        from_sale = False

        if product_data_line_id:
            common_log_line_obj.create_common_log_line_ept(shopify_instance_id=instance.id,module="shopify_ept",
                                                           message=message,
                                                           model_name=model_name,
                                                           shopify_product_data_queue_line_id=product_data_line_id.id)
            product_data_line_id.write({"state": "failed", "last_process_date": datetime.now()})
        elif order_data_line_id:
            common_log_line_obj.create_common_log_line_ept(shopify_instance_id=instance.id,module="shopify_ept",
                                                           message=message,
                                                           model_name=model_name,
                                                           shopify_order_data_queue_line_id=order_data_line_id.id)
            order_data_line_id.write({"state": "failed", "processed_at": datetime.now()})
            from_sale = True

        if create_activity and (order_data_line_id or product_data_line_id):
            if from_sale:
                queue_line = order_data_line_id
            else:
                queue_line = product_data_line_id

            shopify_product_queue_obj.create_schedule_activity_for_product(queue_line, from_sale)

        return True

    def get_product_category(self, product_type):
        """
        Search for product category and create if not found.
        @author: Maulik Barad on Date 01-Sep-2020.
        """
        product_category_obj = self.env["product.category"]

        product_category = product_category_obj.search([("name", "=", product_type),
                                                        ("is_shopify_product_cat", "=", True)],
                                                       limit=1)
        if not product_category:
            product_category = product_category_obj.search([("name", "=", product_type)], limit=1)
            if not product_category:
                product_category = product_category_obj.create({"name": product_type,
                                                                "is_shopify_product_cat": True})

        return product_category

    def shopify_sync_products(self, product_data_line_id, shopify_tmpl_id, instance,
                              order_data_line_id=False):
        """
        This method is used to sync products from queue line or shopify template id for Order.
        @param product_data_line_id: Product Queue Line.
        @param shopify_tmpl_id: Id of shopify template, to import particular product, when not found while processing
        the order.
        @param instance: Shopify Instance.
        @param order_data_line_id: Order Queue Line, when needed to import a product for a order.
        @author: Maulik Barad on Date 01-Sep-2020.
        """
        model_name = "shopify.product.template.ept"
        instance.connect_in_shopify()

        template_data, skip_existing_product = self.convert_shopify_template_response(shopify_tmpl_id,
                                                                                      product_data_line_id, model_name,
                                                                                      order_data_line_id, instance)

        if not template_data:
            return True

        _logger.info("Process started for Product- %s || %s.", template_data.get("id"), template_data.get("title"))

        product_category = self.get_product_category(template_data.get("product_type"))

        shopify_template = self.search(
            [("shopify_tmpl_id", "=", template_data.get("id")),
             ("shopify_instance_id", "=", instance.id)])

        if shopify_template:
            shopify_template = self.sync_product_with_existing_template(shopify_template, skip_existing_product,
                                                                        template_data, instance,
                                                                        product_category, model_name,
                                                                        product_data_line_id,
                                                                        order_data_line_id)
            if not skip_existing_product and instance.sync_product_with_images and shopify_template and \
                    shopify_template.shopify_tmpl_id:
                shopify_template.shopify_sync_product_images(template_data)
        else:
            shopify_template = self.sync_new_product(template_data, instance, product_category, model_name,
                                                     product_data_line_id, order_data_line_id)
            if shopify_template and instance.sync_product_with_images and shopify_template.shopify_tmpl_id:
                shopify_template.shopify_sync_product_images(template_data)

        if shopify_template and product_data_line_id:
            product_data_line_id.write(
                {"state": "done", "last_process_date": datetime.now()})
        if shopify_template:
            self.update_weight_product_variants(instance, shopify_template, template_data.get("variants"))

        _logger.info("Process completed of Product- %s || %s.", template_data.get("id"), template_data.get("title"))

        return shopify_template

    def update_weight_product_variants(self, instance, shopify_template, variant_data):
        for variant in variant_data:
            company_uom = instance._default_UOM_category()
            weight = instance.shopify_product_uom_id._compute_quantity(variant.get("weight"),
                                                                       company_uom)
            product_varinat = shopify_template.product_tmpl_id.product_variant_ids.filtered(
                lambda x: x.default_code == variant.get('sku'))
            product_varinat.write({'weight': weight})

    def convert_shopify_template_response(self, shopify_tmpl_id, product_data_line_id, model_name,
                                          order_data_line_id, instance):
        """ This method is used to convert product response in proper formate.
            @return:template_data, skip_existing_product
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 22 October 2020 .
            Task_id: 167537
        """
        skip_existing_product = False
        if shopify_tmpl_id and not product_data_line_id:
            result = self.import_product_for_order(shopify_tmpl_id, order_data_line_id, model_name, instance)
            if not result:
                return False

            remove_dict_result = result.pop()
            template_data = remove_dict_result.to_dict()
        else:
            template_data = product_data_line_id.synced_product_data
            template_data = json.loads(template_data)
            skip_existing_product = product_data_line_id.product_data_queue_id.skip_existing_product

        return template_data, skip_existing_product

    def sync_product_with_existing_template(self, shopify_template, skip_existing_product, template_data, instance,
                                            product_category, model_name, product_data_line_id,
                                            order_data_line_id):
        """
        This method is used for importing existing template.
        @author: Maulik Barad on Date 03-Sep-2020.
        """
        if skip_existing_product:
            return shopify_template

        template_vals = self.shopify_prepare_template_dic(template_data, instance, product_category)
        variant_data = template_data.get("variants")

        self.create_or_update_shopify_template(template_vals, len(variant_data), shopify_template)

        variant_ids, need_to_archive = self.sync_variant_data_with_existing_template(instance, variant_data,
                                                                                     template_data, shopify_template,
                                                                                     template_vals,
                                                                                     product_data_line_id,
                                                                                     order_data_line_id,
                                                                                     model_name)
        if need_to_archive:
            products_to_archive = shopify_template.shopify_product_ids.filtered(
                lambda x: int(x.variant_id) not in variant_ids)
            products_to_archive.write({"active": False})
        return shopify_template if len(variant_ids) == len(variant_data) else False

    def sync_variant_data_with_existing_template(self, instance, variant_data, template_data, shopify_template,
                                                 template_vals, product_data_line_id, order_data_line_id, model_name):
        """ This method is used to sync Shopify variant data in which the Shopify template is existing in Odoo.
            @return: variant_ids, need_to_archive
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 22 October 2020 .
            Task_id: 167537
        """
        need_to_archive = False
        variant_ids = []
        shopify_product_obj = self.env["shopify.product.product.ept"]
        shopify_attributes = template_data.get("options")
        odoo_template = shopify_template.product_tmpl_id
        name = template_vals.get("template_title", "")
        for variant in variant_data:
            variant_id = variant.get("id")
            sku = variant.get("sku")
            barcode = variant.get("barcode")

            message = self.check_sku_barcode(sku, barcode, name, variant_id, instance.shopify_sync_product_with)
            if message:
                self.create_log_line_for_queue_line(instance, message, model_name, product_data_line_id,
                                                    order_data_line_id, sku)
                continue
            # Here we are not passing SKU and Barcode while searching shopify product, Because We
            # are updating same existing product so.
            shopify_product, odoo_product = self.shopify_search_odoo_product_variant(instance, variant_id, False, False)
            variant_vals = self.prepare_variant_vals(instance, variant)
            domain = [("variant_id", "=", False), ("shopify_instance_id", "=", instance.id),
                      ("shopify_template_id", "=", shopify_template.id)]
            if not shopify_product:
                domain.append(("default_code", "=", sku))
                shopify_product = shopify_product_obj.search(domain, limit=1)

            if not shopify_product:
                domain.append(("product_id.barcode", "=", barcode))
                shopify_product = shopify_product_obj.search(domain, limit=1)

                if not shopify_product:
                    attribute_value_domain = self.find_template_attribute_values(shopify_attributes, odoo_template.id,
                                                                                 variant)
                    if attribute_value_domain:
                        odoo_product = odoo_product.search(attribute_value_domain)

                message = self.is_product_importable(template_data, instance, odoo_product, shopify_product)
                if message:
                    self.create_log_line_for_queue_line(instance, message, model_name, product_data_line_id,
                                                        order_data_line_id, sku, create_activity=True)
                    break

                if odoo_product:
                    shopify_product = self.create_or_update_shopify_variant(variant_vals, shopify_product,
                                                                            shopify_template, odoo_product)

                elif not shopify_product:
                    shopify_product, odoo_product = self.shopify_search_odoo_product_variant(instance, variant_id, sku,
                                                                                             False)
                    shopify_product = self.create_or_update_shopify_variant(variant_vals, shopify_product,
                                                                            shopify_template, odoo_product)
                    if not shopify_product:
                        if instance.auto_import_product:
                            if odoo_template.attribute_line_ids:
                                shopify_product = self.check_for_new_variant(odoo_template, shopify_attributes, variant,
                                                                             shopify_template, variant_vals)
                            else:
                                attribute_line_data = self.prepare_attribute_line_data_for_variant(shopify_attributes,
                                                                                                   variant)
                                odoo_product = self.shopify_create_simple_product(name, variant,
                                                                                  template_vals.get("body_html"),
                                                                                  attribute_line_data)

                                need_to_archive = True
                                shopify_template, shopify_product = self.create_or_update_shopify_template_and_variant(
                                    template_vals, variant_vals, len(variant_data), shopify_template, shopify_product,
                                    odoo_product, update_template=True, update_variant=True)

                            if isinstance(shopify_product, str):
                                message = shopify_product
                                self.create_log_line_for_queue_line(instance, message, model_name, product_data_line_id,
                                                                    order_data_line_id, sku, create_activity=True)
                                variant_ids = []
                                break
                        else:
                            if instance.shopify_sync_product_with == "sku":
                                message = "Product %s not found for SKU %s in Odoo." % (name, sku)
                            elif instance.shopify_sync_product_with == "barcode":
                                message = "Product %s not found for Barcode %s in Odoo." % (name, barcode)
                            else:
                                message = "Product %s not found for SKU %s and Barcode %s in Odoo." % (name, sku, barcode)

                            self.create_log_line_for_queue_line(instance, message, model_name, product_data_line_id,
                                                                order_data_line_id, sku)
                            continue
                else:
                    if instance.shopify_sync_product_with == "sku":
                        message = "Product %s not found for SKU %s in Odoo." % (name, sku)
                    elif instance.shopify_sync_product_with == "barcode":
                        message = "Product %s not found for Barcode %s in Odoo." % (name, barcode)
                    else:
                        message = "Product %s not found for SKU %s and Barcode %s in Odoo." % (name, sku, barcode)

                    self.create_log_line_for_queue_line(instance, message, model_name, product_data_line_id,
                                                        order_data_line_id, sku)
                    continue
            else:
                self.create_or_update_shopify_variant(variant_vals, shopify_product)
            instance.shopify_pricelist_id.set_product_price_ept(shopify_product.product_id.id, variant.get("price"))
            variant_ids.append(variant_id)

        return variant_ids, need_to_archive

    def sync_new_product(self, template_data, instance, product_category, model_name, product_data_line_id,
                         order_data_line_id):
        """
        This method is used for importing new products from Shopify to Odoo.
        @author: Maulik Barad on Date 05-Sep-2020.
        Migration done by Meera Sidapara 24/09/2021.
        """
        shopify_product_obj = self.env["shopify.product.product.ept"]
        need_to_update_template = True
        shopify_template = False

        variant_data = template_data.get("variants")
        template_vals = self.shopify_prepare_template_dic(template_data, instance, product_category)
        name = template_vals.get("template_title")
        odoo_template = False
        for variant in variant_data:
            variant_id = variant.get("id")
            sku = variant.get("sku")
            barcode = variant.get("barcode")
            shopify_product, odoo_product = self.shopify_search_odoo_product_variant(instance, variant_id, sku, barcode)
            if odoo_product:
                odoo_template = odoo_product.product_tmpl_id
        for variant in variant_data:
            variant_id = variant.get("id")
            sku = variant.get("sku")
            barcode = variant.get("barcode")

            message = self.check_sku_barcode(sku, barcode, name, variant_id, instance.shopify_sync_product_with)
            if message:
                self.create_log_line_for_queue_line(instance, message, model_name, product_data_line_id,
                                                    order_data_line_id, sku)
                continue

            variant_vals = self.prepare_variant_vals(instance, variant)

            shopify_product, odoo_product = self.shopify_search_odoo_product_variant(instance, variant_id, sku, barcode)

            message = self.is_product_importable(template_data, instance, odoo_product, shopify_product)
            if message:
                self.create_log_line_for_queue_line(instance, message, model_name, product_data_line_id,
                                                    order_data_line_id, sku, create_activity=True)
                break

            if shopify_product:
                self.create_or_update_shopify_variant(variant_vals, shopify_product, shopify_template)
                if need_to_update_template:
                    shopify_template = self.create_or_update_shopify_template(template_vals, len(variant_data),
                                                                              shopify_product.shopify_template_id,
                                                                              odoo_product, False)
            elif odoo_product:
                shopify_template, shopify_product = self.create_or_update_shopify_template_and_variant(
                    template_vals, variant_vals, len(variant_data), shopify_template, shopify_product, odoo_product,
                    update_template=need_to_update_template, update_variant=True)
                need_to_update_template = False

            elif instance.auto_import_product:
                shopify_attributes = template_data.get("options")
                if odoo_template and odoo_template.attribute_line_ids:
                    if not shopify_template:
                        shopify_template = self.create_or_update_shopify_template(template_vals, len(variant_data),
                                                                                  False,
                                                                                  False, odoo_template)
                    shopify_product = self.check_for_new_variant(odoo_template, shopify_attributes, variant,
                                                                 shopify_template, variant_vals)
                    need_to_update_template = False
                else:
                    if shopify_attributes[0].get("name") == "Title" and \
                            shopify_attributes[0].get("values") == ["Default Title"] and len(variant_data) == 1:
                        odoo_product = self.shopify_create_simple_product(name, variant, template_vals.get("body_html"))
                    else:
                        odoo_template = shopify_product_obj.shopify_create_variant_product(template_data, instance,
                                                                                           variant.get("price"))
                        attribute_value_domain = self.find_template_attribute_values(shopify_attributes,
                                                                                     odoo_template.id,
                                                                                     variant)
                        odoo_product = odoo_template.product_variant_ids.search(attribute_value_domain)

                    shopify_template, shopify_product = self.create_or_update_shopify_template_and_variant(
                        template_vals, variant_vals, len(variant_data), shopify_template, shopify_product, odoo_product,
                        update_template=True, update_variant=True)
                    need_to_update_template = False
                if isinstance(shopify_product, str):
                    message = shopify_product
                    self.create_log_line_for_queue_line(instance, message, model_name, product_data_line_id,
                                                        order_data_line_id, sku, create_activity=True)
                    continue
            else:
                if instance.shopify_sync_product_with == "sku":
                    message = "Product %s not found for SKU %s in Odoo." % (name, sku)
                elif instance.shopify_sync_product_with == "barcode":
                    message = "Product %s not found for Barcode %s in Odoo." % (name, barcode)
                else:
                    message = "Product %s not found for SKU %s and Barcode %s in Odoo." % (name, sku, barcode)

                self.create_log_line_for_queue_line(instance, message, model_name, product_data_line_id,
                                                    order_data_line_id, sku)
                continue

            if need_to_update_template and shopify_template:
                shopify_template = self.create_or_update_shopify_template(template_vals, len(variant_data),
                                                                          shopify_template)
                need_to_update_template = False

            instance.shopify_pricelist_id.set_product_price_ept(shopify_product.product_id.id, variant.get("price"))

            if instance.shopify_compare_pricelist_id:
                instance.shopify_compare_pricelist_id.set_product_price_ept(shopify_product.product_id.id, variant.get("compare_at_price"))


        return shopify_template

    def check_sku_barcode(self, sku, barcode, name, variant_id, match_by):
        """
        This method is used to check for sku and barcode as per configuration in Settings for matching products.
        @param match_by: Configuration of matching products by SKU or Barcode.
        @param variant_id: Shopify variant Id.
        @param name: Name of the product.
        @param sku: SKU of variant.
        @param barcode: Barcode of variant.
        @author: Maulik Barad on Date 26-Nov-2020.
        """
        message = ""
        if match_by == "sku" and not sku:
            message = "Product %s have no sku having variant id %s." % (name, variant_id)
        elif match_by == "barcode" and not barcode:
            message = "Product %s have no barcode having variant id %s." % (name, variant_id)
        elif match_by == "sku_or_barcode" and not sku and not barcode:
            message = "Product %s have no sku and barcode having variant id %s." % (name, variant_id)
        return message

    def create_or_update_shopify_template_and_variant(self, template_vals, variant_vals, variant_length,
                                                      shopify_template, shopify_product, odoo_product,
                                                      update_template=False, update_variant=False):
        """
        This method is used to create or update shopify template and/or variant.
        @author: Maulik Barad on Date 05-Sep-2020.
        """
        if update_template:
            shopify_template = self.create_or_update_shopify_template(template_vals, variant_length, shopify_template,
                                                                      odoo_product)

        if update_variant:
            shopify_product = self.create_or_update_shopify_variant(variant_vals, shopify_product, shopify_template,
                                                                    odoo_product)

        return shopify_template, shopify_product
    def check_for_new_variant(self, odoo_template, shopify_attributes, variant_data, shopify_template, variant_vals):
        """
        Checks if the shopify product has new attribute is added.
        If new attribute is not added then we can add value and generate new variant in Odoo.
        @author: Maulik Barad on Date 04-Sep-2020.
        """
        product_attribute_value_obj = self.env["product.attribute.value"]
        odoo_product_obj = self.env["product.product"]

        counter = 0
        sku = variant_data.get("sku")
        odoo_attribute_lines = odoo_template.attribute_line_ids.filtered(
            lambda x: x.attribute_id.create_variant == "always")

        if len(odoo_attribute_lines) != len(shopify_attributes):
            message = "Product %s has tried to add new attribute for sku %s in Odoo." % (shopify_template.name, sku)
            return message

        attribute_value_domain = self.find_template_attribute_values(shopify_attributes, odoo_template.id, variant_data)
        if not attribute_value_domain:
            for shopify_attribute in shopify_attributes:
                counter += 1
                attribute_name = "option" + str(counter)
                attribute_value = variant_data.get(attribute_name)

                attribute_id = odoo_attribute_lines.filtered(
                    lambda x: x.display_name == shopify_attribute.get("name")).attribute_id.id
                value_id = \
                    product_attribute_value_obj.get_attribute_values(attribute_value, attribute_id, auto_create=True)[
                        0].id

                attribute_line = odoo_attribute_lines.filtered(lambda x: x.attribute_id.id == attribute_id)
                if value_id not in attribute_line.value_ids.ids:
                    attribute_line.value_ids = [(4, value_id, False)]

            odoo_template._create_variant_ids()
        attribute_value_domain = self.find_template_attribute_values(shopify_attributes, odoo_template.id, variant_data)
        odoo_product = odoo_product_obj.search(attribute_value_domain)

        if not odoo_product:
            message = "Unknown error occurred. Couldn't find product %s with sku %s in Odoo." % (
                shopify_template.name, sku)
            return message

        shopify_product = self.create_or_update_shopify_variant(variant_vals, False, shopify_template, odoo_product)
        return shopify_product

    def prepare_attribute_line_data_for_variant(self, shopify_attributes, variant_data):
        """
        Prepares attribute line's data for creating product having single variant.
        @author: Maulik Barad on Date 08-Sep-2020.
        @param shopify_attributes: Attribute data of shopify template.
        @param variant_data: Data of variant.
        """
        product_attribute_obj = self.env['product.attribute']
        product_attribute_value_obj = self.env['product.attribute.value']

        attribute_line_data = []
        counter = 0

        for shopify_attribute in shopify_attributes:
            counter += 1
            attribute_name = "option" + str(counter)
            shopify_attribute_value = variant_data.get(attribute_name)

            attribute = product_attribute_obj.get_attribute(shopify_attribute.get("name"), auto_create=True)
            attribute_value = product_attribute_value_obj.get_attribute_values(shopify_attribute_value, attribute.id,
                                                                               auto_create=True)
            if attribute_value:
                attribute_value = attribute_value[0]
                attribute_line_vals = (
                    0, False, {'attribute_id': attribute.id, 'value_ids': [[6, False, attribute_value.ids]]})
                attribute_line_data.append(attribute_line_vals)

        return attribute_line_data

    def create_or_update_shopify_variant(self, variant_vals, shopify_product, shopify_template=False,
                                         odoo_product=False):
        """
        This method used to create new or update existing shopify variant into Odoo.
        @author: Maulik Barad on Date 03-Sep-2020.
        """
        shopify_product_obj = self.env["shopify.product.product.ept"]

        if not shopify_product and shopify_template and odoo_product:
            variant_vals.update({"name": odoo_product.name,
                                 "product_id": odoo_product.id,
                                 "shopify_template_id": shopify_template.id})

            shopify_product = shopify_product_obj.create(variant_vals)
            if not odoo_product.default_code:
                odoo_product.default_code = shopify_product.default_code

        elif shopify_product:
            if not shopify_product.shopify_template_id.exported_in_shopify and not \
                    shopify_product.shopify_template_id.shopify_tmpl_id and shopify_template:
                variant_vals.update({'shopify_template_id': shopify_template.id})
                shopify_product.shopify_template_id.write({'active': False})
            shopify_product.write(variant_vals)

        return shopify_product

    def shopify_sync_product_images(self, template_data):
        """
        Author: Bhavesh Jadav 18/12/2019
        This method use for sync image from store and the add reference in shopify.product.image.ept
        param:instance:use for the shopify instance its type should be object
        param:template_data usr for the product response its type should be dict
        param:shopify_template use for the shopify template  its type should be object
        param:shopify_product use for the shopify product its type should be object
        param: template_image_updated its boolean for the manage update template image only one time

        @change: By Maulik Barad on Date 28-May-2020.
        When image was removed from Shopify store and then product is imported, the image was not
        removing from Shopify layer.
        Example : 1 image for template, removed from Shopify store, imported the product and not
        removed in layer. So far, when no images come in response, those were not removing
        from layer.
        @version: Shopify 13.0.0.23
        """
        shopify_product_image_obj = shopify_product_images = self.env["shopify.product.image.ept"]
        existing_common_template_images = {}
        is_template_image_set = bool(self.product_tmpl_id.image_1920)
        i = 0
        for odoo_image in self.product_tmpl_id.ept_image_ids:
            i += 1
            if i % 500 == 0: self.env.cache.invalidate()
            odoo_image.read(['image'])
            if not odoo_image.image:
                continue
            key = hashlib.md5(odoo_image.image).hexdigest()
            if not key:
                continue
            existing_common_template_images.update({key: odoo_image.id})
        for image in template_data.get("images", {}):
            if image.get("src"):
                shopify_image_id = str(image.get("id"))
                url = image.get("src")
                variant_ids = image.get("variant_ids")

                if not variant_ids:
                    # below method is used to sync simple product images.
                    shopify_product_images += self.sync_simple_product_images(shopify_image_id,
                                                                              existing_common_template_images, url)
                else:
                    # The below method is used to sync variable(variation) product images.
                    shopify_product_images += self.sync_variable_product_images(shopify_image_id, url, variant_ids,
                                                                                is_template_image_set)

        all_shopify_product_images = shopify_product_image_obj.search([("shopify_template_id",
                                                                        "=", self.id)])
        need_to_remove = all_shopify_product_images - shopify_product_images
        need_to_remove.unlink()
        _logger.info("Images Updated for shopify %s", self.name)
        return True

    def sync_simple_product_images(self, shopify_image_id, existing_common_template_images, url):
        """
        This method is used to create images in the Shopify image layer and common product image layer for the
        simple product.
        :param shopify_image_id: Id of the image as received from image response.
        :param existing_common_template_images: it is used
        @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 22 October 2020 .
        Task_id: 167537
        """
        shopify_product_images = self.env["shopify.product.image.ept"]
        shopify_product_image = self.search_shopify_product_images(self.id, False, shopify_image_id, False)
        if not shopify_product_image:
            try:
                response = requests.get(url, stream=True, verify=True, timeout=10)
                if response.status_code == 200:
                    image = base64.b64encode(response.content)
                    key = hashlib.md5(image).hexdigest()
                    if key in existing_common_template_images.keys():
                        shopify_product_image = self.create_shopify_layer_image(shopify_image_id,
                                                                                existing_common_template_images, key,
                                                                                False)
                    else:
                        if not self.product_tmpl_id.image_1920:
                            self.product_tmpl_id.image_1920 = image
                            common_product_image = self.product_tmpl_id.ept_image_ids.filtered(
                                lambda x: x.image == self.product_tmpl_id.image_1920)
                        else:
                            common_product_image = self.create_common_product_image(image, url, False)
                        shopify_product_image = self.search_shopify_product_images(self.id, False, False,
                                                                                   common_product_image.id)
                        if shopify_product_image:
                            shopify_product_image.shopify_image_id = shopify_image_id
            except Exception:
                pass
        shopify_product_images += shopify_product_image

        return shopify_product_images

    def search_shopify_product_images(self, shopify_template_id, shopify_variant_id, shopify_image_id,
                                      common_product_image):
        """ This method is used to search the shopify images from shopify product images ept table.
            :param shopify_image_id: Id of the image as received from image response.
            @return: shopify_product_image
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 22 October 2020 .
            Task_id: 167537
        """
        shopify_product_image_obj = self.env["shopify.product.image.ept"]

        shopify_product_image = shopify_product_image_obj.search(
            [("shopify_template_id", "=", shopify_template_id),
             ("shopify_variant_id", "=", shopify_variant_id),
             ("shopify_image_id", "=", shopify_image_id),
             ("odoo_image_id", "=", common_product_image)])

        return shopify_product_image

    def create_shopify_layer_image(self, shopify_image_id, existing_common_template_images, key, shopify_product):
        """ This method is used to create a image in shopify image table.
            :param shopify_image_id: Id of the image as received from image response.
            :param existing_common_template_images: Dictionary of existing common template images.
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 22 October 2020 .
            Task_id: 167537
        """
        shopify_product_image_obj = self.env["shopify.product.image.ept"]

        shopify_product_image = shopify_product_image_obj.create({
            "shopify_template_id": self.id,
            "shopify_image_id": shopify_image_id,
            "odoo_image_id": existing_common_template_images[key],
            "shopify_variant_id": shopify_product.id if shopify_product else False,
        })

        return shopify_product_image

    def create_common_product_image(self, image, url, shopify_product):
        """ This method is used to create a image in shopify image table.
            :param image: Binary data of image.
            :param url: URL of the image.
            @return: common_product_image
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 22 October 2020 .
            Task_id: 167537
        """
        common_product_image_obj = self.env["common.product.image.ept"]

        common_product_image = common_product_image_obj.create({
            "name": self.name,
            "template_id": self.product_tmpl_id.id,
            "image": image, "url": url,
            "product_id": shopify_product.product_id.id if shopify_product else False,
        })
        return common_product_image

    def sync_variable_product_images(self, shopify_image_id, url, variant_ids, is_template_image_set):
        """ This method is used to sync images of the variable products.
            :param variant_ids: An array of variant ids associated with the image.
            :param is_template_image_set: It is used to identify that the odoo template has already image set or not.
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 22 October 2020 .
            Task_id: 167537
        """
        shopify_product_images = self.env["shopify.product.image.ept"]
        shopify_products = self.shopify_product_ids.filtered(lambda x: int(x.variant_id) in variant_ids)
        for shopify_product in shopify_products:
            existing_common_variant_images = {}
            for odoo_image in shopify_product.product_id.ept_image_ids:
                if not odoo_image.image:
                    continue
                key = hashlib.md5(odoo_image.image).hexdigest()
                if not key:
                    continue
                existing_common_variant_images.update({key: odoo_image.id})
            shopify_product_image = self.search_shopify_product_images(False, shopify_product.id, shopify_image_id,
                                                                       False)
            if not shopify_product_image:
                try:
                    response = requests.get(url, stream=True, verify=True, timeout=10)
                    if response.status_code == 200:
                        image = base64.b64encode(response.content)
                        key = hashlib.md5(image).hexdigest()
                        if key in existing_common_variant_images.keys():
                            shopify_product_image = self.create_shopify_layer_image(shopify_image_id,
                                                                                    existing_common_variant_images,
                                                                                    key, shopify_product)
                        else:
                            if not shopify_product.product_id.image_1920 or not is_template_image_set:
                                shopify_product.product_id.image_1920 = image
                                common_product_image = shopify_product.product_id.ept_image_ids.filtered(
                                    lambda x: x.image == shopify_product.product_id.image_1920)

                            else:
                                common_product_image = self.create_common_product_image(image, url, shopify_product)

                            shopify_product_image = self.search_shopify_product_images(self.id, shopify_product.id,
                                                                                       False, common_product_image.id)
                            if shopify_product_image:
                                shopify_product_image.shopify_image_id = shopify_image_id
                except Exception:
                    pass
            shopify_product_images += shopify_product_image

        return shopify_product_images

    def shopify_prepare_template_dic(self, template_data, instance, product_category):
        """
        This method used to prepare a shopify template dictionary.
        @param product_category:
        @param instance:
        @param template_data: Data of Shopify Template.
        @author: Maulik Barad on Date 01-Sep-2020.
        """
        shopify_tag_obj = self.env["shopify.tags"]
        tag_ids = []
        sequence = 0
        product_type = 'product'

        for tag in template_data.get("tags").split(","):
            shopify_tag = shopify_tag_obj.search([("name", "=", tag)], limit=1)
            if not shopify_tag:
                sequence = sequence + 1
                shopify_tag = shopify_tag_obj.create({"name": tag, "sequence": sequence})
            sequence = shopify_tag.sequence if shopify_tag else 0
            tag_ids.append(shopify_tag.id)

        for new_template in template_data.get('variants'):
            if not new_template.get('requires_shipping'):
                product_type = 'service'

        if template_data.get('published_at'):
            if template_data.get("published_scope") == "global":
                website_published = "published_global"
            else:
                website_published = "published_web"
        else:
            website_published = "unpublished"

        template_dict = {"shopify_instance_id": instance.id,
                         "template_title": template_data.get("title"),
                         "body_html": template_data.get("body_html"),
                         "product_type": product_type,
                         "tags": tag_ids,
                         "shopify_tmpl_id": template_data.get("id"),
                         "shopify_product_category": product_category.id if product_category else False,
                         "created_at": self.convert_shopify_date_into_odoo_format(
                             template_data.get("created_at")),
                         "updated_at": self.convert_shopify_date_into_odoo_format(
                             template_data.get("updated_at")),
                         "published_at": self.convert_shopify_date_into_odoo_format(
                             template_data.get("published_at")),
                         "website_published": website_published,
                         "active": True}

        return template_dict

    def convert_shopify_date_into_odoo_format(self, product_date):
        """
        This method used to convert shopify product date into odoo date time format
        :return shopify product date
        @author: Nilesh Parmar @Emipro Technologies Pvt. Ltd on date 2/11/2019
        """
        shopify_product_date = False
        if not product_date:
            return shopify_product_date
        shopify_product_date = parser.parse(product_date).astimezone(utc).strftime("%Y-%m-%d %H:%M:%S")
        return shopify_product_date

    def shopify_search_odoo_product_variant(self, shopify_instance, variant_id, product_sku, barcode):
        """
        Searches for Shopify/Odoo product with SKU and/or Barcode.
        @param shopify_instance: It is the browsable object of shopify instance
        @param product_sku : It is the default code of product and its type is String
        @param variant_id : It is the id of the product variant and its type is Integer
        @param barcode: Barcode from Shopify product.
        @author: Maulik Barad on Date 01-Sep-2020.
        """
        odoo_product = self.env["product.product"]
        shopify_product_obj = self.env["shopify.product.product.ept"]

        shopify_product = shopify_product_obj.search([("variant_id", "=", variant_id),
                                                      ("shopify_instance_id", "=", shopify_instance.id)],
                                                     limit=1)

        if shopify_instance.shopify_sync_product_with == "sku" and product_sku:
            if not shopify_product:
                shopify_product = shopify_product_obj.search([("default_code", "=", product_sku),
                                                              ("variant_id", "=", False),
                                                              ("shopify_instance_id", "=", shopify_instance.id)],
                                                             limit=1)
            if not shopify_product:
                shopify_product = shopify_product_obj.search(
                    [("product_id.default_code", "=", product_sku),
                     ("variant_id", "=", False),
                     ("shopify_instance_id", "=", shopify_instance.id)], limit=1)
            if not shopify_product:
                odoo_product = odoo_product.search([("default_code", "=", product_sku)], limit=1)

        elif shopify_instance.shopify_sync_product_with == "barcode" and barcode:
            if not shopify_product:
                shopify_product = shopify_product_obj.search(
                    [("product_id.barcode", "=", barcode),
                     ("variant_id", "=", False),
                     ("shopify_instance_id", "=", shopify_instance.id)], limit=1)
            if not shopify_product:
                odoo_product = odoo_product.search([("barcode", "=", barcode)], limit=1)

        elif shopify_instance.shopify_sync_product_with == "sku_or_barcode":
            if product_sku:
                if not shopify_product:
                    shopify_product = shopify_product_obj.search([("default_code", "=", product_sku),
                                                                  ("variant_id", "=", False),
                                                                  ("shopify_instance_id", "=", shopify_instance.id)],
                                                                 limit=1)
                if not shopify_product:
                    shopify_product = shopify_product_obj.search([("product_id.default_code", "=", product_sku),
                                                                  ("variant_id", "=", False),
                                                                  ("shopify_instance_id", "=", shopify_instance.id)],
                                                                 limit=1)
                if not shopify_product:
                    odoo_product = odoo_product.search([("default_code", "=", product_sku)], limit=1)

            if not odoo_product and not shopify_product and barcode:
                shopify_product = shopify_product_obj.search(
                    [("product_id.barcode", "=", barcode),
                     ("shopify_instance_id", "=", shopify_instance.id)], limit=1)
                if not shopify_product:
                    odoo_product = odoo_product.search([("barcode", "=", barcode)], limit=1)

        if shopify_product and not odoo_product:
            odoo_product = shopify_product.product_id

        return shopify_product, odoo_product

    def create_or_update_shopify_template(self, template_dict, variant_length, shopify_template, odoo_product=False,
                                          odoo_template=False):
        """
        This method used to create new or update existing shopify template into Odoo.
        @param : self, template_dict, shopify_template, template_data, odoo_product
        @return: shopify_template
        @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 11/10/2019.
        @migrate : Maulik Barad on Date 03-Sep-2020.
        """
        vals = {
            "shopify_instance_id": template_dict.get("shopify_instance_id"),
            "name": template_dict.get("template_title"),
            "shopify_tmpl_id": template_dict.get("shopify_tmpl_id"),
            "created_at": template_dict.get("created_at"),
            "updated_at": template_dict.get("updated_at"),
            "description": template_dict.get("body_html"),
            "published_at": template_dict.get("published_at"),
            "website_published": template_dict.get("website_published"),
            "exported_in_shopify": True,
            "total_variants_in_shopify": variant_length,
            "shopify_product_category": template_dict.get("shopify_product_category"),
            "tag_ids": [(6, 0, template_dict.get("tags"))]}

        if shopify_template:
            shopify_template.write(vals)
        else:
            if odoo_product:
                vals.update({"product_tmpl_id": odoo_product.product_tmpl_id.id})
            elif odoo_template:
                vals.update({'product_tmpl_id': odoo_template.id})
            shopify_template = self.create(vals)

        return shopify_template

    def is_product_importable(self, template_data, instance, odoo_product, shopify_product):
        """
        This method will check if the product can be imported or not.
        @author: Maulik Barad on Date 03-Sep-2020.
        Changes done by Meera Sidapara on Date 26-Feb-2022.
        """
        odoo_product_obj = self.env["product.product"]
        shopify_product_obj = self.env["shopify.product.product.ept"]

        message = ""
        variants = template_data.get("variants")
        template_title = template_data.get("title", "")
        template_id = template_data.get("id", "")

        shopify_skus = []
        shopify_barcodes = []
        shopify_product_ids_list = []
        for variant in variants:
            variant_id = variant.get("id") or False
            sku = variant.get("sku", "")
            barcode = variant.get("barcode", "")
            sku and shopify_skus.append(sku)
            barcode and shopify_barcodes.append(barcode)
            if barcode:
                duplicate_barcode = odoo_product_obj.search([("barcode", "=", barcode)])
                shopify_variant = shopify_product_obj.search([
                    ("shopify_instance_id", "=", instance.id),
                    ("variant_id", "=", variant_id)])
                shopify_product_ids = shopify_product_obj.search(
                    [("shopify_instance_id", "=", instance.id), ("exported_in_shopify", "=", False),
                     ('product_id.barcode', '=', barcode)])
                shopify_product_ids_list.append(shopify_product_ids)
                if duplicate_barcode and shopify_variant and shopify_variant.product_id and \
                        shopify_variant.product_id.id != duplicate_barcode.id:
                    message = "Duplicate barcode(%s) found in Product: %s and ID: %s." % (barcode, template_title,
                                                                                          template_id)
                    return message
                # elif not instance.auto_import_product and not shopify_product_ids and \
                #         instance.shopify_sync_product_with not in ["barcode", "sku_or_barcode"]:
                #     message = "Duplicate barcode(%s) found in Product: %s and ID: %s." % (barcode, template_title,
                #                                                                           template_id)
                #     return message
                # elif instance.auto_import_product and duplicate_barcode:
                #     message = "Duplicate barcode(%s) found in Product: %s and ID: %s." % (barcode, template_title,
                #                                                                           template_id)
                #     return message

        total_shopify_sku = len(set(shopify_skus))
        if len(shopify_skus) != total_shopify_sku:
            message = "Duplicate SKU found in Product %s and ID: %s." % (template_title, template_id)
            return message

        total_shopify_barcodes = len(set(shopify_barcodes))
        if len(shopify_barcodes) != total_shopify_barcodes:
            message = "Duplicate Barcode found in Product %s and ID: %s." % (template_title, template_id)
            return message

        if not odoo_product and not shopify_product and instance.shopify_sync_product_with in ["barcode",
                                                                                               "sku_or_barcode"]:
            if not shopify_product_ids_list:
                message = "Duplicate barcode found in Product: %s and ID: %s." % (template_title, template_id)
                return message

        return message

    def shopify_publish_unpublish_product(self):
        """
        This method is used to publish/unpublish product in shopify store from the the shopify product form view in
        odoo.
        """
        common_log_line_obj = self.env["common.log.lines.ept"]
        published_at = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
        instance = self.shopify_instance_id
        instance.connect_in_shopify()
        if self.shopify_tmpl_id:
            try:
                new_product = shopify.Product.find(self.shopify_tmpl_id)
                if new_product:
                    new_product.id = self.shopify_tmpl_id
                    if self._context.get("publish") == "shopify_unpublish":
                        new_product.published_scope = "null"
                        new_product.published_at = None
                    elif self._context.get("publish") == "shopify_publish_global":
                        new_product.published_scope = "global"
                        new_product.published_at = published_at
                    else:
                        new_product.published_scope = "web"
                        new_product.published_at = published_at
                    result = new_product.save()
                    if result:
                        result_dict = new_product.to_dict()
                        updated_at = self.convert_shopify_date_into_odoo_format(result_dict.get("updated_at"))
                        if self._context.get("publish") == "shopify_unpublish":
                            self.write(
                                {"updated_at": updated_at, "published_at": False, "website_published": "unpublished"})
                        else:
                            published_at = self.convert_shopify_date_into_odoo_format(result_dict.get("published_at"))
                            if result_dict.get('published_at'):
                                if result_dict.get("published_scope") == "global":
                                    website_published = "published_global"
                                else:
                                    website_published = "published_web"
                            else:
                                website_published = "unpublished"

                            self.write({"updated_at": updated_at, "published_at": published_at,
                                        "website_published": website_published})
            except:
                message = "Template %s not found in shopify When Publish" % self.shopify_tmpl_id
                common_log_line_obj.create_common_log_line_ept(shopify_instance_id=instance.id,module="shopify_ept",
                                                               message=message,
                                                               model_name="shopify.product.template.ept")

    def action_product_ref_redirect(self):
        """
        This method is used to redirect Shopify product in shopify Store.
        @author: Yagnik Joshi on Date 11-January-2023.
        @Task: 190111 - Shopify APP features
        """
        self.ensure_one()
        url = '%s/admin/products/%s' % (self.shopify_instance_id.shopify_host, self.shopify_tmpl_id)
        return {
            'type': 'ir.actions.act_url',
            'url': url,
            'target': 'new',
        }
