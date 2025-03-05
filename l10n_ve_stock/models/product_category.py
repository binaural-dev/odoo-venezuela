import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class ProductCategory(models.Model):
    _inherit = "product.category"
    _check_company_auto = True

    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)
