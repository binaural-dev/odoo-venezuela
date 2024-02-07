from odoo import models, fields, api, _
from odoo.exceptions import UserError

import logging

_logger = logging.getLogger(__name__)
class SaleOrder(models.Model):
    _inherit = 'sale.order'

    seller_id = fields.Many2one(
        "hr.employee",
        string="Seller",
        tracking=True,
        store=True,
        help="Partner's seller reference."
    )

    def action_confirm(self):
        res = super().action_confirm()
        multiple_seller_config = self.env.company.multiple_sellers
        for order in self:
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
                    if order.seller_id:
                        return
                    seller_name = ""
                    for seller in order.partner_id.seller_ids:
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
        self.seller_id = (
            self.partner_id.seller_ids[0] if len(self.partner_id.seller_ids) == 1 else False
        )