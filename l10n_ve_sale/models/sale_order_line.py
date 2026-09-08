from odoo import api, fields, models, _
from odoo.tools import float_round
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

    # override
    @api.depends("product_id", "product_uom_id", "product_uom_qty","order_id.currency_id")
    def _compute_price_unit(self):
        def has_manual_price(line):
            # `line.currency_id` can be False for NewId records
            currency = (
                line.currency_id or
                line.order_id.currency_id
                or line.company_id.currency_id
                or line.env.company.currency_id
            )
            return currency.compare_amounts(line.technical_price_unit, line.price_unit)

        force_recompute = self.env.context.get('force_price_recomputation')
        for line in self:
            # Don't compute the price for deleted lines or lines for which the
            # price unit doesn't come from the product.
            if not line.order_id or line.is_downpayment or line._is_global_discount():
                continue

            # check if the price has been manually set or there is already invoiced amount.
            # if so, the price shouldn't change as it might have been manually edited.
            if (
                (not force_recompute and has_manual_price(line))
                or line.qty_invoiced > 0
                or (line.product_id.expense_policy == 'cost' and line.is_expense)
            ):
                continue
            line = line.with_context(sale_write_from_compute=True)
            if not line.product_uom_id or not line.product_id:
                line.price_unit = 0.0
                line.technical_price_unit = 0.0
            else:
                line._reset_price_unit()
    @api.depends("invoice_lines.move_id.state", "invoice_lines.quantity")
    def _compute_invoiced(self):
        for line in self:
            invoice_lines = line._get_invoice_lines()
            invoiced = invoice_lines and all(
                invoice_line.move_id.move_type == "out_invoice"
                for invoice_line in invoice_lines
            )
            line.invoiced = invoiced

    @api.depends(
        "price_unit",
        "order_id.date_order",
        "order_id.foreign_rate_date",
        "currency_id",
        "company_id",
    )
    def _compute_foreign_price(self):
        for line in self:

            # foreign_rate_date es la fecha de la que salio la tasa de la orden
            # y sobrevive a que el core reescriba date_order al confirmar. Sin
            # esto la linea se recalculaba con la fecha de confirmacion aunque
            # la tasa de la orden estuviera congelada.
            order_date = (
                line.order_id.foreign_rate_date
                or line.order_id.date_order
                or fields.Date.today()
            )

            company_currency = line.company_id.currency_id
            foreign_currency = line.company_id.foreign_currency_id
            line_currency = line.currency_id or line.order_id.currency_id or line.company_id.currency_id

            if not line_currency or not foreign_currency:
                line.foreign_price = 0.0
                continue

            if line_currency.id == foreign_currency.id:
                line.foreign_price = line.price_unit
                continue

            # round=False + redondeo a la precision del campo: _convert()
            # redondea por defecto a los decimales de la moneda destino
            # (USD = 2), pero foreign_price usa "Foreign Product Price",
            # cuya precision es configurable.
            # Sin esto un precio unitario pequeño se pierde al convertir, y
            # el valor de la orden no coincide con el de la factura que sale
            # de ella (account.move.line usa el mismo criterio).
            precision = self.env["decimal.precision"].precision_get(
                "Foreign Product Price"
            )
            line.foreign_price = float_round(
                line_currency._convert(
                    line.price_unit,
                    foreign_currency,
                    line.company_id,
                    order_date,
                    round=False,
                ),
                precision_digits=precision,
            )

    @api.depends("product_uom_qty", "foreign_price", "discount", "tax_ids")
    def _compute_foreign_subtotal(self):
        """Subtotal en moneda alterna.

        Mismo criterio que account.move.line: cuando hay impuestos se pasa por
        compute_all para que el subtotal sea la base real (descuenta el
        impuesto si va incluido en el precio) y quede redondeado a la moneda
        alterna. Sin impuestos es la multiplicacion directa.
        """
        for line in self:
            line_discount_price_unit = line.foreign_price * (
                1 - (line.discount / 100.0)
            )
            foreign_subtotal = line_discount_price_unit * line.product_uom_qty

            if line.tax_ids:
                taxes_res = line.tax_ids.compute_all(
                    line_discount_price_unit,
                    quantity=line.product_uom_qty,
                    currency=line.foreign_currency_id,
                    product=line.product_id,
                    partner=line.order_id.partner_id,
                )
                line.foreign_subtotal = taxes_res["total_excluded"]
            else:
                line.foreign_subtotal = foreign_subtotal

    
    def _prepare_foreign_base_line_for_taxes_computation(self):
        """ Convert the current record to a dictionary in order to use the generic taxes computation method
        defined on account.tax.

        :return: A python dictionary.
        """
        self.ensure_one()
        return self.env['account.tax']._prepare_foreign_base_line_for_taxes_computation(
            self,
            price_unit=self.foreign_price,
            tax_ids=self.tax_ids,
            quantity=self.product_uom_qty,
            partner_id=self.order_id.partner_id,
            currency_id=self.order_id.currency_id or self.order_id.company_id.currency_id,
            rate=getattr(self.order_id, 'currency_rate', 1.0),
        )
