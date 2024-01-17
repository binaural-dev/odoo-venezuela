from odoo import fields, models, _
from odoo.exceptions import ValidationError

import logging

_logger = logging.getLogger(__name__)

class SaleOrder(models.Model):
    _inherit = "sale.order"

    def action_confirm(self):
        for order in self:
            if order.subsidiary_id.id != order.warehouse_id.subsidiary_id.id:
                raise ValidationError(_("The budget subsidiary must be the same Warehouse subsidiary."))
        return super().action_confirm()