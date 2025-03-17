from odoo import api, models, _
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    @api.constrains("product_id", "order_id", "order_id.is_consignation")
    def _check_product_in_consignation(self):
        for line in self:
            warehouse = line.order_id.warehouse_id
            if warehouse and warehouse.is_consignation_warehouse:
                picking_location = self.env["stock.quant"].search_count(
                    [
                        ("product_id", "=", line.product_id.id),
                        ("location_id.partner_id", "=", line.order_id.partner_id.id),
                        ("location_id.usage", "=", "internal"),
                        ("quantity", ">", 0),
                    ]
                )
                if picking_location == 0:
                    raise ValidationError(
                        _("The product is not available in the customer's consignation location.")
                    )

    @api.constrains("product_uom_qty")
    def _check_quantity_in_consignation(self):
        for line in self:
            warehouse = line.order_id.warehouse_id
            if warehouse and warehouse.is_consignation_warehouse:
                stock_available = self.env["stock.quant"].read_group(
                    domain=[
                        ("product_id", "=", line.product_id.id),
                        ("location_id.partner_id", "=", line.order_id.partner_id.id),
                        ("location_id.usage", "=", "internal"),
                    ],
                    fields=["quantity:sum"],
                    groupby=[],
                )
                total_stock = stock_available[0]["quantity"] if stock_available else 0

                if line.product_uom_qty > total_stock:
                    raise ValidationError(
                        _("Cannot sell more than the available consignation stock.")
                    )
