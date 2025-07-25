from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

import logging

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    is_donation = fields.Boolean(string="Is Donation", default=False, tracking=True)
    
    ### CONSTRAINTS ###
    @api.constrains("is_donation", "state")
    def _check_is_donation(self):
        for order in self:
            if (order.state in ["sale", "done"]) and order._origin:
                if order.is_donation != order._origin.is_donation:
                    raise ValidationError(
                        _(
                            "The field 'Is Donation' cannot be modified on a confirmed or completed order."
                        )
                    )
