from odoo import api, fields, models
import logging

_logger = logging.getLogger(__name__)


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    latest_standard_price = fields.Monetary(compute="_compute_latest_standard_price", store=True)

    update_latest_standard_price = fields.Boolean(
        related="product_id.product_tmpl_id.update_last_cost", readonly=False
    )

    price_per_udm = fields.Float(
        string="Price per unit", compute="_compute_price_per_udm", required=False, default=0
    )

    @api.depends("product_id")
    def _compute_latest_standard_price(self):
        for line in self:
            latest_standard_price = line.product_id.latest_standard_price
            line.latest_standard_price = latest_standard_price

    @api.depends("price_unit", "product_uom")
    def _compute_price_per_udm(self):
        """
        This compute update
        """
        for line in self:
            line.price_per_udm = 0
            if line.product_id and line.product_uom and line.price_unit > 0:
                line.price_per_udm = line.price_unit / line.product_uom.factor_inv
