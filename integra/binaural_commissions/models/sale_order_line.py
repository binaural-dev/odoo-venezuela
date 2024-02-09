from odoo import api, fields, models, _
from collections import defaultdict


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    commission_policy_line_image_ids = fields.Many2many(
        "commission.policy.line.image", string="Policy Line Images", index=True, copy=False
    )

    @api.model
    def get_commission_policy_line_image(self,days):
        for line in self.commission_policy_line_image_ids:
            if line.date_from <= days <= line.date_to:
                return line
        return False
