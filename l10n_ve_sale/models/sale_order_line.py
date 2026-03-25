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
        "currency_id",
        "company_id",
    )
    def _compute_foreign_price(self):
        for line in self:

            order_date = line.order_id.date_order or fields.Date.today()

            company_currency = line.company_id.currency_id
            foreign_currency = line.company_id.foreign_currency_id
            if line.currency_id.id == company_currency.id:
                line.foreign_price = line.currency_id._convert(
                    line.price_unit,
                    foreign_currency,
                    line.company_id,
                    order_date,
                )
            elif line.currency_id.id == foreign_currency.id:
                line.foreign_price = line.price_unit
            else:
                price_in_company = line.currency_id._convert(
                    line.price_unit,
                    company_currency,
                    line.company_id,
                    order_date,
                )
                line.foreign_price = company_currency._convert(
                    price_in_company,
                    foreign_currency,
                    line.company_id,
                    order_date,
                )

    @api.depends("product_uom_qty", "foreign_price", "discount")
    def _compute_foreign_subtotal(self):
        for line in self:
            line_discount_price_unit = line.foreign_price * (
                1 - (line.discount / 100.0)
            )
            line.foreign_subtotal = line_discount_price_unit * line.product_uom_qty
