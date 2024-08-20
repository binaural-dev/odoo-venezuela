from odoo import models, fields, api, _
from odoo.exceptions import UserError

import logging

_logger = logging.getLogger(__name__)
class SaleOrder(models.Model):
    _inherit = 'sale.order'

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
        for sale in self:
            if not sale.partner_id:
                sale.sellers_available = False
            sale.sellers_available = sale.partner_id.seller_ids

    def action_confirm(self):
        res = super().action_confirm()
        multiple_seller_config = self.env.company.multiple_sellers
        for order in self:
            if order.seller_id or not order.company_seller:
                continue

            if not order.partner_id.seller_ids:
                    raise UserError(_("The customer must have at least one salesperson assigned"))
            if len(order.partner_id.seller_ids) == 1:
                order.seller_id = order.partner_id.seller_ids[0]
            if len(order.partner_id.seller_ids) > 1:
                if not multiple_seller_config:
                    raise UserError(
                        _(
                            "This client has several sellers assigned to him, configure a single seller in his contact form"
                        )
                    )
                else:
                    seller_name = ""
                    for seller in order.sellers_available:
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
            return
        self.seller_id = False
