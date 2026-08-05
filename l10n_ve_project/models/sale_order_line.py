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

    @api.depends(
        'foreign_subtotal',
        'qty_to_invoice',
        'product_uom_qty',
        'invoice_lines',
        'invoice_lines.parent_state',
        'invoice_lines.foreign_balance',
    )
    def _compute_foreign_amount_split(self):
        """Split the foreign amount of the sale order line.

        ``foreign_amount_invoiced`` is the amount that has actually been
        invoiced, read from the foreign_balance of the linked invoice lines
        (the "real invoiced" criterion). ``foreign_amount_to_invoice`` is a
        forecast, prorated from the order foreign subtotal using
        ``qty_to_invoice``, mirroring the core ``untaxed_amount_to_invoice``.
        """
        for line in self:
            if line.product_uom_qty:
                line.foreign_amount_invoiced = sum(
                    -invoice_line.foreign_balance
                    for invoice_line in line.invoice_lines
                    if invoice_line.parent_state != 'cancel'
                )
                line.foreign_amount_to_invoice = line.foreign_subtotal * line.qty_to_invoice / line.product_uom_qty
            else:
                line.foreign_amount_invoiced = 0.0
                line.foreign_amount_to_invoice = 0.0
