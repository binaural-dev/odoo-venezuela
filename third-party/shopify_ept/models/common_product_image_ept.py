# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

import logging

from odoo import models, api

_logger = logging.getLogger("Shopify Common Image")


class ProductImageEpt(models.Model):
    _inherit = 'common.product.image.ept'

    @api.model_create_multi
    def create(self, vals):
        """
        Inherited create method for adding images in shopify image layer.
        @author: Bhavesh Jadav on Date 17-Dec-2019.
        """
        results = super(ProductImageEpt, self).create(vals)
        for result in results:
            if self.user_has_groups('shopify_ept.group_shopify_ept'):
                shopify_product_image_obj = self.env["shopify.product.image.ept"]
                shopify_product_image_vals = {"odoo_image_id": result.id}
                if result.product_id:
                    shopify_variants = self.env['shopify.product.product.ept'].search_read(
                        [('product_id', '=', result.product_id.id)], ["id", "shopify_template_id"])
                    for shopify_variant in shopify_variants:
                        shopify_product_image_vals.update({"shopify_variant_id": shopify_variant["id"],
                                                           "shopify_template_id":
                                                               shopify_variant["shopify_template_id"][0],
                                                           "sequence": 0})
                        shopify_product_image_obj.create(shopify_product_image_vals)

                elif result.template_id:
                    if self._context.get("main_image"):
                        shopify_product_image_vals.update({"sequence": 0})
                    shopify_templates = self.env["shopify.product.template.ept"].search_read(
                        [("product_tmpl_id", "=", result.template_id.id)], ["id"])
                    for shopify_template in shopify_templates:
                        shopify_product_image_vals.update({'shopify_template_id': shopify_template["id"]})
                        shopify_product_image_obj.create(shopify_product_image_vals)
        return results

    def write(self, vals):
        """
        Inherited write method for adding images in Shopify products.
        @author: Bhavesh Jadav on Date 17-Dec-2019.
        """
        result = super(ProductImageEpt, self).write(vals)
        if self.user_has_groups('shopify_ept.group_shopify_ept'):
            shopify_product_images = self.env["shopify.product.image.ept"]
            for record in self:
                shopify_product_images += shopify_product_images.search([("odoo_image_id", "=", record.id)])
            if shopify_product_images:
                if not vals.get("product_id", ""):
                    shopify_product_images.write({'shopify_variant_id': False})
                elif vals.get("product_id", ""):
                    for shopify_product_image in shopify_product_images:
                        shopify_variant = self.env["shopify.product.product.ept"].search_read(
                            [("product_id", "=", vals.get("product_id")),
                             ("shopify_template_id", "=", shopify_product_image.shopify_template_id.id)], ["id"])
                        if shopify_variant:
                            shopify_product_image.write({"shopify_variant_id": shopify_variant["id"]})
        return result
