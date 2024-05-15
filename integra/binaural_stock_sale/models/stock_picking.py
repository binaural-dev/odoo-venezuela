from odoo import api, fields, models, _

from odoo.exceptions import ValidationError
from odoo.exceptions import UserError

import logging

_logger = logging.getLogger(__name__)

class StockPicking(models.Model):
    _inherit = "stock.picking"

    sale_order_id = fields.Many2one("sale.order")
    sale_invoice = fields.Char(compute="_compute_sale_invoice")
    sale_user_id = fields.Many2one(related='sale_order_id.user_id')

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        res.set_sale_pos_order()
        return res
    
    def set_sale_pos_order(self):
        for stock in self:
            if stock.origin and not stock.sale_order_id:
                sale_order = self.env["sale.order"].search(
                    [
                        ("name", "=", stock.origin),
                        ("company_id", "=", self.env.company.id),
                    ]
                )
                if sale_order:
                    stock.sale_order_id = sale_order

    def _compute_sale_invoice(self):
        for stock in self:
            stock.sale_invoice = ""
            if stock.sale_order_id:
                if stock.sale_order_id.invoice_ids:
                    invoice_one = True
                    name_invoice = ""
                    for invoice in stock.sale_order_id.invoice_ids:
                        if not invoice_one:
                            name_invoice += f", {invoice.name}"
                            continue
                        name_invoice = invoice.name
                        invoice_one = False
                    stock.sale_invoice = name_invoice