from odoo import api, fields, models, _
import logging
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_is_zero



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

    @api.depends("price_unit", "order_id.foreign_inverse_rate", "order_id.currency_id")
    def _compute_foreign_price(self):
        """
        Computes the foreign price unit for the sale order line applying strict alternate logic.
        Uses standard, English-compliant abstract variable names.
        """
        for line in self:
            # Initialize to prevent CacheMiss errors
            line.foreign_price = 0.0
            
            # Skip non-product lines (sections, notes) or zero prices
            if line.display_type or not line.price_unit:
                continue
                
            order = line.order_id
            foreign_currency = self.env.company.currency_foreign_id
            
            if not order or not foreign_currency:
                continue

            # Extract the alternate inverse rate from the header safely
            inverse_rate = order.foreign_inverse_rate if hasattr(order, "foreign_inverse_rate") else 0.0
            
            # Fallback security: use day rate if current record rate is not yet set
            if inverse_rate <= 0.0:
                inverse_rate = foreign_currency._get_conversion_rate(
                    self.env.company.currency_id,
                    foreign_currency,
                    self.env.company,
                    order.date_order or fields.Date.today(),
                ) or 1.0

            # =========================================================================
            # CORRECT CURRENCY CONVERSION MATRIX (Odoo Standard Convention)
            # =========================================================================
            company_currency = self.env.company.currency_id
            document_currency = line.currency_id

            if document_currency == company_currency:
                # If the document is in Company Currency (e.g., Base), 
                # we MULTIPLY by the inverse rate to get the alternate value.
                line.foreign_price = foreign_currency.round(line.price_unit * inverse_rate)
            else:
                # If the document is already in Foreign/Alternate Currency,
                # we DIVIDE by the inverse rate to bring it back to the company's base value.
                line.foreign_price = foreign_currency.round(line.price_unit / inverse_rate) if inverse_rate else 0.0

    @api.depends("product_uom_qty", "foreign_price", "discount")
    def _compute_foreign_subtotal(self):
        for line in self:
            discount = line.discount if line.discount and not float_is_zero(line.discount, precision_digits=2) else 0.0

            price_with_discount = line.foreign_price * (1 - (discount / 100.0))
            foreign_subtotal_teoric = price_with_discount * line.product_uom_qty

           
            if foreign_subtotal_teoric > 0.0 and line.price_subtotal > 0.0:
                line.foreign_subtotal = foreign_subtotal_teoric
                
                porcion_total_con_iva = line.price_total / line.price_subtotal
                
                if hasattr(line, 'foreign_price_total'):
                    line.foreign_price_total = foreign_subtotal_teoric * porcion_total_con_iva
            else:
                line.foreign_subtotal = foreign_subtotal_teoric
                if hasattr(line, 'foreign_price_total'):
                    line.foreign_price_total = foreign_subtotal_teoric
            
    def _prepare_invoice_line(self, **optional_values):
       
        res = super(SaleOrderLine, self)._prepare_invoice_line(**optional_values)
        res['foreign_subtotal'] = self.foreign_subtotal
        res['foreign_price'] = self.foreign_price
        res['foreign_inverse_rate'] = self.foreign_inverse_rate
        res['foreign_currency_id'] = self.foreign_currency_id.id
        return res