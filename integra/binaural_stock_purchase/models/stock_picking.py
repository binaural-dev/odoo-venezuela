from odoo import api, fields, models, _

from odoo.exceptions import ValidationError
from odoo.exceptions import UserError

import logging

_logger = logging.getLogger(__name__)

class StockPicking(models.Model):
    _inherit = "stock.picking"

    purchase_order_id = fields.Many2one("purchase.order")
    purchase_invoice = fields.Char(compute="_compute_purchase_invoice")

    def set_sale_pos_order(self):
        res = super().set_sale_pos_order()
        for stock in self:
            if not stock.sale_order_id and not stock.purchase_order_id and stock.origin:
                purchase_order = self.env["purchase.order"].search(
                    [
                        ("name", "=", stock.origin),
                        ("company_id", "=", self.env.company.id),
                    ]
                )
                if purchase_order:
                    stock.purchase_order_id = purchase_order
        return res
    
    def _compute_purchase_invoice(self):
        for stock in self:
            stock.purchase_invoice = ""
            if stock.purchase_order_id:
                if stock.purchase_order_id.invoice_ids:
                    invoice_one = True
                    name_invoice = ""
                    for invoice in stock.purchase_order_id.invoice_ids:
                        if not invoice_one:
                            name_invoice += f", {invoice.name}"
                            continue
                        name_invoice = invoice.name
                        invoice_one = False
                    stock.purchase_invoice = name_invoice
