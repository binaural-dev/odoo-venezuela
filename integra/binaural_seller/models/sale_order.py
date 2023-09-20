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
            if len(order.partner_id.seller_ids) > 1 and not multiple_seller_config:
                raise UserError(_("This client has several sellers assigned to him, configure a single seller in his contact form"))
        return res