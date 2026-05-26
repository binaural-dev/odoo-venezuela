from odoo import api, fields, models, _
import logging
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_is_zero, float_round



_logger = logging.getLogger(__name__)


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    foreign_currency_id = fields.Many2one(
        related="order_id.foreign_currency_id", store=True
    )
    foreign_rate = fields.Float(related="order_id.foreign_rate", store=True)
    foreign_inverse_rate = fields.Float(

        related="order_id.foreign_inverse_rate",
        store=True
    )

    foreign_price = fields.Float(
        help="Foreign Price of the line",
        compute="_compute_foreign_price",
        digits="Foreign Product Price",
        store=True,
        readonly=False
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

    

    @api.depends("order_id.foreign_inverse_rate")
    def _compute_foreign_inverse_rate(self):
        for record in self:
            valor_orden = record.order_id.foreign_inverse_rate or 0.0
            if record.foreign_inverse_rate != valor_orden:
                record.foreign_inverse_rate = valor_orden

    @api.depends("price_unit", "foreign_inverse_rate")
    def _compute_foreign_price(self):
        precision = self.env["decimal.precision"].precision_get('Alternate cost')
        for line in self:
            if line.price_unit and line.foreign_inverse_rate:
                if line.foreign_currency_id.id == self.env.ref("base.VEF").id:
                    foreign_inverse_rate = float_round(
                        line.order_id.foreign_inverse_rate, 
                        precision_digits=precision
                    )
                else:
                    foreign_inverse_rate = line.order_id.foreign_inverse_rate
                line.foreign_price = float_round(
                    line.price_unit * foreign_inverse_rate,
                    precision_digits=precision,
                )
            else:
                line.foreign_price = 0.0

    @api.depends("product_uom_qty", "foreign_price", "discount")
    def _compute_foreign_subtotal(self):
        
        for line in self:
            if not line.product_uom_qty or not line.foreign_price:
                line.foreign_subtotal = 0.0
                continue
            
            discount = line.discount if line.discount and not float_is_zero(line.discount, precision_digits=2) else 0.0
            
            price_with_discount = line.foreign_price * (1 - (discount / 100.0))
            
            line.foreign_subtotal = price_with_discount * line.product_uom_qty
            
    def _prepare_invoice_line(self, **optional_values):
       
        res = super(SaleOrderLine, self)._prepare_invoice_line(**optional_values)
        res['foreign_subtotal'] = self.foreign_subtotal
        res['foreign_price'] = self.foreign_price
        res['foreign_inverse_rate'] = self.foreign_inverse_rate
        res['foreign_currency_id'] = self.foreign_currency_id.id
        return res