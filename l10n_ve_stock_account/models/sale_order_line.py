from odoo import api, models, _
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    @api.constrains("product_id", "order_id")
    def _check_product_in_consignation(self):
        for line in self:
            if line.order_id.warehouse_id.is_consignation_warehouse:
                picking_location = self.env["stock.quant"].search(
                    [
                        ("product_id", "=", line.product_id.id),
                        ("location_id.partner_id", "=", line.order_id.partner_id.id),
                        ("location_id.usage", "=", "internal"),
                        ("quantity", ">", 0),
                    ]
                )
                if not picking_location:
                    raise ValidationError(
                        _("The product is not available in the customer's consignation location.")
                    )

    @api.constrains("product_uom_qty")
    def _check_quantity_in_consignation(self):
        for line in self:
            if line.order_id.warehouse_id.is_consignation_warehouse:
                stock_available = sum(
                    self.env["stock.quant"]
                    .search(
                        [
                            ("product_id", "=", line.product_id.id),
                            ("location_id.partner_id", "=", line.order_id.partner_id.id),
                            ("location_id.usage", "=", "internal"),
                        ]
                    )
                    .mapped("quantity")
                )
                if line.product_uom_qty > stock_available:
                    raise ValidationError(
                        _("Cannot sell more than the available consignation stock.")
                    )
