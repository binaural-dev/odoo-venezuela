import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class PriceRule(models.Model):
    _inherit = "delivery.price.rule"

    foreign_list_base_price = fields.Float(digits="Product Price", required=True, default=0.0)
    list_base_price = fields.Float(compute="_compute_base_price")

    def _compute_base_price(self):
        for rule in self:
            pass