# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

import logging
from odoo import models, fields

_logger = logging.getLogger("Shopify Image")


class ShopifyProductImageEpt(models.Model):
    """
    For attaching images with shopify and odoo products.
    @author: Bhavesh Jadav  on Date 16-Dec-2019.
    """
    _name = "shopify.product.image.ept"
    _description = "Shopify Product Image"
    _order = "sequence, create_date desc, id"

    odoo_image_id = fields.Many2one("common.product.image.ept", ondelete="cascade")
    shopify_image_id = fields.Char(string="Shopify Image ID", help="Id of image in Shopify.")
    shopify_variant_id = fields.Many2one("shopify.product.product.ept")
    shopify_template_id = fields.Many2one("shopify.product.template.ept")
    url = fields.Char(related="odoo_image_id.url", help="External URL of image")
    image = fields.Image(related="odoo_image_id.image")
    sequence = fields.Integer(help="Sequence of images.", index=True, default=10)
