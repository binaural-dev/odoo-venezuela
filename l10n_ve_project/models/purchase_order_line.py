# -*- coding: utf-8 -*-

from odoo import api, fields, models


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    foreign_currency_id = fields.Many2one(related="order_id.foreign_currency_id", store=True)
    foreign_rate = fields.Float(related="order_id.foreign_rate", store=True)
    foreign_inverse_rate = fields.Float(related="order_id.foreign_inverse_rate", store=True)

    foreign_price = fields.Float(
        help="Foreign Price of the line",
        compute="_compute_foreign_price",
        digits="Foreign Product Price",
        store=True,
        readonly=False,
    )
    foreign_subtotal = fields.Monetary(
        help="Foreign Subtotal of the line",
        compute="_compute_foreign_subtotal",
        currency_field="foreign_currency_id",
        store=True,
    )

    foreign_amount_to_bill = fields.Monetary(
        string="Foreign To Bill",
        compute="_compute_foreign_amount_split",
        currency_field="foreign_currency_id",
        store=True,
    )
    foreign_amount_billed = fields.Monetary(
        string="Foreign Billed",
        compute="_compute_foreign_amount_split",
        currency_field="foreign_currency_id",
        store=True,
    )

    @api.depends("price_unit", "currency_id", "order_id.date_order")
    def _compute_foreign_price(self):
        """Convert the line unit price to the foreign currency.

        Uses the rate of the order date (``order_id.date_order``) through the
        standard ``res.currency._convert``.
        """
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
                line.foreign_price = line.currency_id._convert(
                    line.price_unit,
                    foreign_currency,
                    line.company_id,
                    order_date,
                )

    @api.depends("product_qty", "foreign_price", "discount")
    def _compute_foreign_subtotal(self):
        """Compute the foreign subtotal of the line.

        Applies the line discount over the foreign unit price and multiplies
        by the ordered quantity.
        """
        for line in self:
            line_discount_price_unit = line.foreign_price * (
                1 - (line.discount / 100.0)
            )
            line.foreign_subtotal = line_discount_price_unit * line.product_qty

    @api.depends(
        "foreign_subtotal",
        "invoice_lines",
        "invoice_lines.move_id.move_type",
        "invoice_lines.parent_state",
        "invoice_lines.foreign_balance",
    )
    def _compute_foreign_amount_split(self):
        """Split the foreign amount of the purchase order line.

        Mirrors the monetary criterion used by the project profitability
        panel (``project.project._get_purchase_order_foreign_amounts``):
        ``foreign_amount_billed`` is the real amount invoiced (posted invoice
        lines), and ``foreign_amount_to_bill`` is the committed subtotal minus
        what has already been reflected in non-refund invoice lines (posted
        or not). This avoids dropping to 0 when the quantity is fully
        invoiced but the invoiced amount doesn't match the order subtotal
        (price/rate mismatches, partial credit notes).
        """
        for line in self:
            invoice_lines = line.invoice_lines.filtered(lambda l: l.parent_state != 'cancel')
            total_invoiced = 0.0
            billed = 0.0
            for inv_line in invoice_lines:
                cost = inv_line.foreign_balance
                if inv_line.move_id.move_type not in ('in_refund', 'out_refund'):
                    total_invoiced += cost
                if inv_line.parent_state == 'posted':
                    billed += cost
            line.foreign_amount_billed = billed
            line.foreign_amount_to_bill = (line.foreign_subtotal or 0.0) - total_invoiced
