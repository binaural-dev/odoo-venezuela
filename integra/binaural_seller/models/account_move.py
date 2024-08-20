from odoo import fields, models, api, _
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = "account.move"

    def _get_domain_seller(self):
        return (
            "[('is_seller', '=',True)]" if not self.env.company.restrict_seller
            else "[('id', 'in', sellers_available)]"
        )
    
    sellers_available = fields.Many2many(
        "hr.employee",
        compute="_compute_sellers_available"
    )

    seller_id = fields.Many2one(
        "hr.employee",
        string="Seller",
        tracking=True,
        store=True,
        help="Partner's seller reference.",
        domain=_get_domain_seller,
    )

    company_seller = fields.Boolean(
        related='company_id.company_seller',
    )

    @api.depends("partner_id")
    def _compute_sellers_available(self):
        for invoice in self:
            if not invoice.partner_id:
                invoice.sellers_available = False
            invoice.sellers_available = invoice.partner_id.seller_ids

    @api.model_create_multi
    def create(self, vals_list):
        invoices = super().create(vals_list)
        for invoice in invoices:
            if invoice.invoice_origin and invoice.move_type == "out_invoice" and invoice.company_seller:
                sale_order = self.env["sale.order"].search(
                    [
                        ("name", "=", invoice.invoice_origin),
                        ("company_id", "=", self.env.company.id),
                    ]
                )
                invoice.seller_id = sale_order.seller_id.id
        return invoices

    def action_post(self):
        res = super().action_post()
        multiple_seller_config = self.env.company.multiple_sellers
        for invoice in self:
            if (
                not invoice.seller_id
                and invoice.move_type
                in (
                    "out_invoice",
                    "out_refund",
                    "out_receipt",
                )
                and invoice.company_seller
            ):
                if not invoice.partner_id.seller_ids:
                    raise UserError(_("The customer must have at least one salesperson assigned"))
                if len(invoice.partner_id.seller_ids) == 1:
                    invoice.seller_id = invoice.partner_id.seller_ids[0]
                if len(invoice.partner_id.seller_ids) > 1:
                    if not multiple_seller_config:
                        raise UserError(
                            _(
                                "This client has several sellers assigned to him, configure a single seller in his contact form"
                            )
                        )
                    else:
                        if invoice.seller_id:
                            return
                        seller_name = ""
                        for seller in invoice.sellers_available:
                            seller_name += seller.name + ", "
                        raise UserError(
                            _(
                                "El contacto seleccionado posee estos Vendedores: %s. Debe elegir uno.",
                                seller_name,
                            )
                        )
        return res

    @api.onchange("partner_id")
    def _onchange_partner_id(self):
        if self.company_seller:
            self.seller_id = (
                self.partner_id.seller_ids[0] if len(self.partner_id.seller_ids) == 1 else False
            )
        self.seller_id = False