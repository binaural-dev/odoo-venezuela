# -*- coding: utf-8 -*-

from odoo import api, fields, models


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    foreign_amount_to_invoice = fields.Monetary(
        string="Foreign To Invoice",
        compute="_compute_foreign_amount_split",
        currency_field="foreign_currency_id",
        store=True,
    )
    foreign_amount_invoiced = fields.Monetary(
        string="Foreign Invoiced",
        compute="_compute_foreign_amount_split",
        currency_field="foreign_currency_id",
        store=True,
    )

    @api.depends('foreign_subtotal', 'qty_invoiced', 'qty_to_invoice', 'product_uom_qty')
    def _compute_foreign_amount_split(self):
        for line in self:
            if line.product_uom_qty:
                line.foreign_amount_invoiced = line.foreign_subtotal * line.qty_invoiced / line.product_uom_qty
                line.foreign_amount_to_invoice = line.foreign_subtotal * line.qty_to_invoice / line.product_uom_qty
            else:
                line.foreign_amount_invoiced = 0.0
                line.foreign_amount_to_invoice = 0.0
