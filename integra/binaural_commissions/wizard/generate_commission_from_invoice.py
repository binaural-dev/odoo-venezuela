from odoo import api, Command, fields, models, _

import logging

_logger = logging.getLogger(__name__)


class GenerateCommission(models.TransientModel):
    _name = "generate.commission.from.invoice"
    _chck_company_auto = True

    company_id = fields.Many2one(
        "res.company", string="Company", default=lambda self: self.env.company, store=False
    )
    invoice_type = fields.Selection(
        [
            ("one2one", "Generate a commission invoice"),
            ("many2one", "Generate an invoice with all commissions"),
        ],
        default="many2one",
        required=True,
    )

    seller_id = fields.Many2one("res.partner", string="Seller", required=True, store=False)
    invoice_ids = fields.Many2many("account.move", store=False)

    def _prepare_invoice_vals(self):
        vals = []
        commission_amount = 0
        for invoice in self.invoice_ids:
            if self.invoice_type == "many2one":
                commission_amount += invoice.total_commission
                continue

            vals.append(
                {
                    "is_commission_invoice": True,
                    "partner_id": self.seller_id.id,
                    "origin_commission_invoice": [invoice.id],
                    "invoice_line_ids": self._prepare_commission_line_vals(
                        invoice.total_commission
                    ),
                }
            )
        if len(vals) > 1 or self.invoice_type == "one2one":
            return vals

        return [
            {
                "is_commission_invoice": True,
                "partner_id": self.seller_id.id,
                "origin_commission_invoice": self.invoice_ids.ids,
                "invoice_line_ids": self._prepare_commission_line_vals(commission_amount),
            }
        ]

    def _prepare_commission_line_vals(self, amount):
        product_id = self.env.company.commission_product_id
        return [
            Command.create(
                {
                    "product_id": product_id.id,
                    "name": "Commission",
                    "price_unit": amount,
                    "quantity": 1,
                    "tax_ids": [(Command.set, 0, product_id.taxes_id.ids)],
                }
            ),
        ]

    def create_invoice(self):
        account_move = self.env["account.move"].with_context({"default_move_type": "in_invoice"})
        invoice_ids = account_move.create(self._prepare_invoice_vals())
        if self.company_id.in_invoice_status_commission == "posted":
            invoice_ids.action_post()
        return {
            "type": "ir.actions.act_window",
            "name": _("Seller invoices"),
            "res_model": "account.move",
            "view_mode": "tree,form",
            "target": "self",
            "domain": [("id", "in", invoice_ids.ids)],
        }
