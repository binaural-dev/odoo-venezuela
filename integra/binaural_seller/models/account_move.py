from odoo import fields, models, api, _
from odoo.exceptions import UserError

import logging

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    seller_id = fields.Many2one(
        "hr.employee",
        string="Seller",
        tracking=True,
        store=True,
        help="Partner's seller reference."
    )

    @api.model_create_multi
    def create(self, vals_list):
        invoices = super().create(vals_list)
        for invoice in invoices:
            if invoice.invoice_origin:
                sale_order = self.env["sale.order"].search([("name", "=", invoice.invoice_origin)])
                invoice.seller_id = sale_order.seller_id.id
        return invoices
    
    def action_post(self):
        res = super().action_post()
        for invoice in self:
            if not invoice.seller_id:
                raise UserError(_("The invoice must have a seller assigned"))
        return res
