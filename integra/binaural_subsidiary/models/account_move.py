import json
import logging

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"
    
    account_analytic_id = fields.Many2one("account.analytic.account", string="Analytic Account")
    
    
    @api.model_create_multi
    def create(self, vals_list):
        invoices = super().create(vals_list)
        for invoice in invoices:
            if invoice.invoice_origin and invoice.move_type in ("out_invoice","out_refund","in_invoice", "in_refund"):
                sale_order = self.env["sale.order"].search(
                    [
                        ("name", "=", invoice.invoice_origin),
                        ("company_id", "=", self.env.company.id),
                    ]
                )
                invoice.account_analytic_id = sale_order.account_analytic_id
        return invoices

        