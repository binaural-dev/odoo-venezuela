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
        for line in self:
            line_discount_price_unit = line.foreign_price * (
                1 - (line.discount / 100.0)
            )
            line.foreign_subtotal = line_discount_price_unit * line.product_qty

    @api.depends("foreign_subtotal", "qty_invoiced", "product_qty")
    def _compute_foreign_amount_split(self):
        for line in self:
            if line.product_qty:
                line.foreign_amount_billed = line.foreign_subtotal * line.qty_invoiced / line.product_qty
                line.foreign_amount_to_bill = line.foreign_subtotal - line.foreign_amount_billed
            else:
                line.foreign_amount_billed = 0.0
                line.foreign_amount_to_bill = 0.0
