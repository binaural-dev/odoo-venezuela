from odoo import api, Command, fields, models, _
from odoo.exceptions import ValidationError

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

    # NO ME DEJA GUARDAR LAS NUEVAS FACTURAS PARA CREAR COMISION

    seller_ids = fields.Many2many(
        "hr.employee", string="Sellers", compute="_compute_seller_ids", store=False
    )
    seller_id = fields.Many2one("res.partner", string="Seller", required=True, store=False)
    invoice_ids = fields.Many2many("account.move")

    @api.depends("invoice_ids")
    def _compute_seller_ids(self):
        for record in self:
            record.seller_ids = record.invoice_ids.seller_id

    def _prepare_invoice_vals(self):
        def default_invoice_data(invoice):
            return {
                "is_commission_invoice": True,
                "partner_id": invoice.seller_id.user_partner_id.id,
                "journal_id": invoice.company_id.commission_journal_id.id,
            }

        vals = []
        invoices_with_commission_invoice = []
        commission_amount = 0
        for invoice in self.invoice_ids:
            if invoice.commission_invoice:
                invoices_with_commission_invoice.append(invoice.name)
                continue

            if self.invoice_type == "many2one":
                commission_amount += invoice.total_commission
                continue

            new_vals = dict()
            new_vals = default_invoice_data(invoice)
            new_vals["invoice_line_ids"] = self._prepare_commission_line_vals(
                invoice.total_commission, invoice
            )
            new_vals["origin_commission_invoice"] = [invoice.id]
            vals.append(new_vals)

        if len(invoices_with_commission_invoice) > 0:
            raise ValidationError(
                _(
                    "The invoices %s already has a commission invoice in process",
                    ", ".join(invoices_with_commission_invoice),
                )
            )

        if len(vals) > 1 or self.invoice_type == "one2one":
            return vals

        if len(self.seller_ids) > 1:
            raise ValidationError(_("The invoices must have the same seller"))

        new_vals = dict()
        new_vals = default_invoice_data(self.invoice_ids)

        new_vals["invoice_line_ids"] = self._prepare_commission_line_vals(commission_amount,self.invoice_ids)
        new_vals["origin_commission_invoice"] = [Command.set(self.invoice_ids.ids)]
        return [new_vals]

    def _prepare_commission_line_vals(self, amount, invoices):
        product_id = self.env.company.commission_product_id
        invoice_names = ", ".join(invoices.mapped("name"))
        return [
            Command.create(
                {
                    "product_id": product_id.id,
                    "name": _("Commission of invoices: %s", invoice_names),
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
