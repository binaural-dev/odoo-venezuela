from odoo import models, fields

import logging
import traceback

_logger = logging.getLogger(__name__)


class ProductTemplate(models.Model):
    _inherit = "product.template"

    commission_item_ids = fields.One2many("commission.product.item", "product_id")

class ProductCategory(models.Model):
    _inherit = "product.category"

    commission_item_ids = fields.One2many("commission.product.item", "category_id")


class ProductBrand(models.Model):
    _inherit = "product.brand"

    commission_item_ids = fields.One2many("commission.product.item", "brand_id")

