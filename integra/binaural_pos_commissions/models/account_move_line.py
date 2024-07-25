from odoo import fields, models

import logging
_logger = logging.getLogger(__name__)


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def get_commission(self, collection_days):
        res = super().get_commission(collection_days)
        if self.pos_order_line_ids:
            return self.pos_order_line_ids.get_commission_policy_line_image(collection_days)

        if not self.pos_order_line_ids and self.move_id.pos_order_ids:
            for line in self.move_id.pos_order_ids.lines:
                if line.product_id == self.product_id:
                    return line.get_commission_policy_line_image(collection_days)
        return res


