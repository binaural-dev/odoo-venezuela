# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

import base64
import logging
import io
from csv import DictWriter
from datetime import datetime
from io import StringIO

from odoo import models, fields, _
from odoo.exceptions import UserError
from odoo.tools.misc import xlsxwriter

_logger = logging.getLogger("Shopify Layer")


class PrepareProductForExport(models.TransientModel):
    """
    Model for adding Odoo products into Shopify Layer.
    @author: Maulik Barad on Date 11-Apr-2020.
    """
    _name = "shopify.prepare.product.for.export.ept"
    _description = "Prepare product for export in Shopify"

    export_method = fields.Selection([("direct", "Export in Shopify Layer"),
                                      ("csv", "Export in CSV file"), ("xlsx", "Export in XLSX file")],
                                     default="direct")
    shopify_instance_id = fields.Many2one("shopify.instance.ept")
    choose_file = fields.Binary(help="Select CSV file to upload.")
    file_name = fields.Char(help="Name of CSV file.")

    def prepare_product_for_export(self):
        """
        This method is used to export products in Shopify layer as per selection.
        If "direct" is selected, then it will direct export product into Shopify layer.
        If "csv" is selected, then it will export product data in CSV file, if user want to do some
        modification in name, description, etc. before importing into Shopify.
        """
        _logger.info("Starting product exporting via %s method...", self.export_method)

        active_template_ids = self._context.get("active_ids", [])
        templates = self.env["product.template"].browse(active_template_ids)
        product_templates = templates.filtered(lambda template: template.detailed_type == "product")
        if not product_templates:
            raise UserError(_("It seems like selected products are not Storable products."))

        if self.export_method == "direct":
            return self.export_direct_in_shopify(product_templates)
        elif self.export_method == "csv":
            return self.export_csv_file(product_templates)
        else:
            return self.export_xlsx_file(product_templates)

    def export_direct_in_shopify(self, product_templates):
        """
        Creates new products or updates existing products in the Shopify layer using the direct export method.
        @author: Maulik Barad on Date 19-Sep-2020.
        """
        shopify_template_id = False
        sequence = 0
        variants = product_templates.product_variant_ids
        shopify_instance = self.shopify_instance_id

        for variant in variants:
            if not variant.default_code:
                continue
            product_template = variant.product_tmpl_id
            if product_template.attribute_line_ids and len(product_template.attribute_line_ids.filtered(
                    lambda x: x.attribute_id.create_variant == "always")) > 3:
                continue
            shopify_template, sequence, shopify_template_id = self.create_or_update_shopify_layer_template(
                shopify_instance, product_template, variant, shopify_template_id, sequence)

            self.create_shopify_template_images(shopify_template)

            if shopify_template and shopify_template.shopify_product_ids and \
                    shopify_template.shopify_product_ids[0].sequence:
                sequence += 1

            shopify_variant = self.create_or_update_shopify_layer_variant(variant, shopify_template_id,
                                                                          shopify_instance, shopify_template, sequence)

            self.create_shopify_variant_images(shopify_template, shopify_variant)
        return True

    def create_or_update_shopify_layer_template(self, shopify_instance, product_template, variant,
                                                shopify_template_id, sequence):
        """ This method is used to create or update the Shopify layer template.
            @return: shopify_template, sequence, shopify_template_id
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 26 October 2020 .
            Task_id: 167537 - Code refactoring
        """
        shopify_templates = shopify_template_obj = self.env["shopify.product.template.ept"]

        shopify_template = shopify_template_obj.search([
            ("shopify_instance_id", "=", shopify_instance.id),
            ("product_tmpl_id", "=", product_template.id)], limit=1)

        if not shopify_template:
            shopify_product_template_vals = self.prepare_template_val_for_export_product_in_layer(product_template,
                                                                                                  shopify_instance,
                                                                                                  variant)
            shopify_template = shopify_template_obj.create(shopify_product_template_vals)
            sequence = 1
            shopify_template_id = shopify_template.id
        else:
            if shopify_template_id != shopify_template.id:
                shopify_product_template_vals = self.prepare_template_val_for_export_product_in_layer(product_template,
                                                                                                      shopify_instance,
                                                                                                      variant)
                shopify_template.write(shopify_product_template_vals)
                shopify_template_id = shopify_template.id
        if shopify_template not in shopify_templates:
            shopify_templates += shopify_template

        return shopify_template, sequence, shopify_template_id

    def prepare_template_val_for_export_product_in_layer(self, product_template, shopify_instance, variant):
        """ This method is used to prepare a template Vals for export/update product
            from Odoo products to the Shopify products layer.
            :param product_template: Record of odoo template.
            :param product_template: Record of instance.
            @return: template_vals
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 26 October 2020 .
            Task_id: 167537 - Code refactoring
        """
        ir_config_parameter_obj = self.env["ir.config_parameter"]
        # template_vals = {"product_tmpl_id": product_template.id,
        #                  "shopify_instance_id": shopify_instance.id,
        #                  "shopify_product_category": product_template.categ_id.id,
        #                  "name": product_template.name}
        # if ir_config_parameter_obj.sudo().get_param("shopify_ept.set_sales_description"):
        #     template_vals.update({"description": variant.description_sale})
        name = product_template.with_context(lang=shopify_instance.shopify_lang_id.code).name
        template_vals = {"product_tmpl_id": product_template.id,
                         "shopify_instance_id": shopify_instance.id,
                         "shopify_product_category": product_template.categ_id.id,
                         "name": name}
        if ir_config_parameter_obj.sudo().get_param("shopify_ept.set_sales_description"):
            description = variant.with_context(lang=shopify_instance.shopify_lang_id.code).description_sale
            template_vals.update({"description": description})
        return template_vals

    def prepare_variant_val_for_export_product_in_layer(self, shopify_instance, shopify_template, variant, sequence):
        """ This method is used to prepare a vals for the variants.
            @return: shopify_variant_vals
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 26 October 2020 .
            Task_id: 167537 - Code refactoring
        """
        shopify_variant_vals = ({
            "shopify_instance_id": shopify_instance.id,
            "product_id": variant.id,
            "shopify_template_id": shopify_template.id,
            "default_code": variant.default_code,
            "name": variant.name,
            "sequence": sequence
        })
        return shopify_variant_vals

    def create_or_update_shopify_layer_variant(self, variant, shopify_template_id, shopify_instance,
                                               shopify_template, sequence):
        """ This method is used to create/update the variant in the shopify layer.
            @return: shopify_variant
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 26 October 2020 .
            Task_id: 167537 - Code refactoring
        """
        shopify_product_obj = self.env["shopify.product.product.ept"]

        shopify_variant = shopify_product_obj.search([
            ("shopify_instance_id", "=", self.shopify_instance_id.id),
            ("product_id", "=", variant.id),
            ("shopify_template_id", "=", shopify_template_id)])

        shopify_variant_vals = self.prepare_variant_val_for_export_product_in_layer(shopify_instance,
                                                                                    shopify_template, variant,
                                                                                    sequence)
        if not shopify_variant:
            shopify_variant = shopify_product_obj.create(shopify_variant_vals)
        else:
            shopify_variant.write(shopify_variant_vals)

        return shopify_variant

    def preapre_product_data_for_file(self, product_templates):
        """
        This method is use to prepare product data for export csv/xlsx file.
        @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 2 December 2021 .
        Task_id: 180489 - Prepare for export changes
        """
        product_data_list = []
        for template in product_templates:
            if template.attribute_line_ids and len(
                    template.attribute_line_ids.filtered(lambda x: x.attribute_id.create_variant == "always")) > 3:
                continue
            if len(template.product_variant_ids.ids) == 1 and not template.default_code:
                continue
            for product in template.product_variant_ids.filtered(lambda variant: variant.default_code):
                product_data = self.prepare_row_data_for_file(template, product)
                product_data_list.append(product_data)

        if not product_data_list:
            raise UserError(_("No data found to be exported.\n\nPossible Reasons:\n   - Number of "
                              "attributes are more than 3.\n   - SKU(s) are not set properly."))
        return product_data_list

    def export_csv_file(self, product_templates):
        """
        This method is used for export the odoo products in csv file.
        :param self: It contain the current class Instance
        :param product_templates: Records of odoo template.
        @author: Nilesh Parmar @Emipro Technologies Pvt. Ltd on date 04/11/2019
        """
        product_data = self.preapre_product_data_for_file(product_templates)
        buffer = StringIO()
        delimiter = ","
        field_names = list(product_data[0].keys())
        csv_writer = DictWriter(buffer, field_names, delimiter=delimiter)
        csv_writer.writer.writerow(field_names)
        csv_writer.writerows(product_data)
        buffer.seek(0)
        file_data = buffer.read().encode()
        self.write({
            "choose_file": base64.encodebytes(file_data),
            "file_name": "Shopify_export_product_"
        })

        return {
            "type": "ir.actions.act_url",
            "url": "web/content/?model=shopify.prepare.product.for.export.ept&id=%s&field=choose_file&download=true&"
                   "filename=%s.csv" % (self.id, self.file_name + str(datetime.now().strftime("%d/%m/%Y:%H:%M:%S"))),
            "target": self
        }

    def export_xlsx_file(self, product_templates):
        """
        This method is use to export the product data in xlsx file.
        @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 2 December 2021 .
        Task_id: 180489 - Prepare for export changes
        """
        product_data = self.preapre_product_data_for_file(product_templates)
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Map Product')
        header = list(product_data[0].keys())
        header_format = workbook.add_format({'bold': True, 'font_size': 10})
        general_format = workbook.add_format({'font_size': 10})
        worksheet.write_row(0, 0, header, header_format)
        index = 0
        for product in product_data:
            index += 1
            worksheet.write_row(index, 0, list(product.values()), general_format)
        workbook.close()
        b_data = base64.b64encode(output.getvalue())
        self.write({
            "choose_file": b_data,
            "file_name": "Shopify_export_product_"
        })
        return {
            "type": "ir.actions.act_url",
            "url": "web/content/?model=shopify.prepare.product.for.export.ept&id=%s&field=choose_file&download=true&"
                   "filename=%s.xlsx" % (self.id, self.file_name + str(datetime.now().strftime("%d/%m/%Y:%H:%M:%S"))),
            "target": self
        }

    def prepare_row_data_for_file(self, template, product):
        """ This method is used to prepare a row data of csv file.
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 26 October 2020 .
            Task_id: 167537 - Code refactoring
        """
        row = {
            "template_name": template.name,
            "product_name": product.name,
            "product_default_code": product.default_code,
            "shopify_product_default_code": product.default_code,
            "product_description": product.description_sale or None,
            "PRODUCT_TEMPLATE_ID": template.id,
            "PRODUCT_ID": product.id,
            "CATEGORY_ID": template.categ_id.id
        }
        return row

    def create_shopify_template_images(self, shopify_template):
        """
        For adding all odoo images into shopify layer only for template.
        @author: Maulik Barad on Date 19-Sep-2020.
        """
        shopify_product_image_list = []
        shopify_product_image_obj = self.env["shopify.product.image.ept"]
        common_product_image_obj = self.env["common.product.image.ept"]

        common_product_images = common_product_image_obj.search(
            [('template_id', '=', shopify_template.product_tmpl_id.id)])
        images = common_product_images.filtered(lambda img: img.image == shopify_template.product_tmpl_id.image_1920)
        if not images and shopify_template.product_tmpl_id.image_1920:
            common_product_image_obj.create({
                "name": shopify_template.name,
                "template_id": shopify_template.product_tmpl_id.id,
                "image": shopify_template.product_tmpl_id.image_1920,
            })
        product_template = shopify_template.product_tmpl_id
        for odoo_image in product_template.ept_image_ids.filtered(lambda x: not x.product_id):
            shopify_product_image = shopify_product_image_obj.search_read(
                [("shopify_template_id", "=", shopify_template.id),
                 ("odoo_image_id", "=", odoo_image.id)], ["id"])
            if not shopify_product_image:
                shopify_product_image_list.append({
                    "odoo_image_id": odoo_image.id,
                    "shopify_template_id": shopify_template.id
                })
        if shopify_product_image_list:
            shopify_product_image_obj.create(shopify_product_image_list)
        return True

    def create_shopify_variant_images(self, shopify_template, shopify_variant):
        """
        For adding first odoo image into shopify layer for variant.
        @author: Maulik Barad on Date 19-Sep-2020.
        """
        shopify_product_image_obj = self.env["shopify.product.image.ept"]
        common_product_image_obj = self.env["common.product.image.ept"]

        common_product_images = common_product_image_obj.search(
            [('product_id', '=', shopify_variant.product_id.id)])
        images = common_product_images.filtered(lambda img: img.image == shopify_variant.product_id.image_1920)
        if not images and shopify_variant.product_id.image_1920:
            common_product_image_obj.create({
                "name": shopify_template.name,
                "template_id": shopify_template.product_tmpl_id.id,
                "image": shopify_variant.product_id.image_1920,
                "product_id": shopify_variant.product_id.id,
            })
        for variant_image in shopify_variant.product_id.ept_image_ids:
            shopify_product_image = shopify_product_image_obj.search_read(
                [("shopify_template_id", "=", shopify_template.id),
                 ("shopify_variant_id", "=", shopify_variant.id),
                 ("odoo_image_id", "=", variant_image.id)], ["id"])
            if not shopify_product_image:
                shopify_product_image_obj.create({
                    "odoo_image_id": variant_image.id,
                    "shopify_variant_id": shopify_variant.id,
                    "shopify_template_id": shopify_template.id,
                    "sequence": 0
                })
        return True
