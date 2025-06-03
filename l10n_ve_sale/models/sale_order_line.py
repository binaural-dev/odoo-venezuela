from odoo import api, fields, models, _
import logging

_logger = logging.getLogger(__name__)


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    foreign_currency_id = fields.Many2one(
        related="order_id.foreign_currency_id", store=True
    )
    foreign_rate = fields.Float(related="order_id.foreign_rate", store=True)
    foreign_inverse_rate = fields.Float(
        related="order_id.foreign_inverse_rate", store=True
    )

    foreign_price = fields.Float(
        help="Foreign Price of the line",
        compute="_compute_foreign_price",
        digits="Foreign Product Price",
        store=True,
    )
    foreign_subtotal = fields.Monetary(
        help="Foreign Subtotal of the line",
        compute="_compute_foreign_subtotal",
        currency_field="foreign_currency_id",
        store=True,
    )

    invoiced = fields.Boolean(compute="_compute_invoiced", store=True, copy=False)

    @api.depends("invoice_lines.move_id.state", "invoice_lines.quantity")
    def _compute_invoiced(self):
        for line in self:
            invoice_lines = line._get_invoice_lines()
            invoiced = invoice_lines and all(
                invoice_line.move_id.move_type == "out_invoice"
                for invoice_line in invoice_lines
            )
            line.invoiced = invoiced

    @api.depends("price_unit", "foreign_inverse_rate")
    def _compute_foreign_price(self):
        for line in self:
            line.foreign_price = line.price_unit * line.foreign_inverse_rate

    @api.depends("product_uom_qty", "foreign_price", "discount")
    def _compute_foreign_subtotal(self):
        for line in self:
            line_discount_price_unit = line.foreign_price * (
                1 - (line.discount / 100.0)
            )
            line.foreign_subtotal = line_discount_price_unit * line.product_uom_qty

    def _action_launch_stock_rule(self, previous_product_uom_qty=False):
        """
         We inherit this method to 
         only propagate to super for the orders that really need a delivery.
        """
        deliverable = self.filtered(lambda l: l.order_id.document != 'invoice')
        if deliverable:
            return super(SaleOrder, deliverable)._action_launch_stock_rule(previous_product_uom_qty)
        
        return True 