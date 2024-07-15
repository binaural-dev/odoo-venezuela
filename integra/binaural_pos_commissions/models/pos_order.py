from odoo import fields, models
import logging
_logger = logging.getLogger(__name__)


class PosOrder(models.Model):
    _inherit = "pos.order"

    def action_pos_order_paid(self):
        res = super().action_pos_order_paid()
        self.assing_commission_policy_line_images_to_order_lines()
        return res

    def assing_commission_policy_line_images_to_order_lines(self):
        self.env["commission.policy"].assing_commission_policy_line_images_to_lines(
            self.lines
        )
