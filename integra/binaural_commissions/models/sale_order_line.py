from odoo import api, fields, models, _
from collections import defaultdict


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    commission_policy_line_image_ids = fields.Many2many(
        "commission.policy.line.image", string="Policy Line Images", index=True, copy=False
    )


#     def assign_commission_policy_line_images(self):

#         for line in self:
#             line.commision_policy_line_image_ids = line.product_id.commision_policy_line_image_ids
#             line.product_id.commision_policy_line_image_ids = False
