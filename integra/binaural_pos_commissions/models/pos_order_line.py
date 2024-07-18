from odoo import api, fields, models


class PosOrderLine(models.Model):
    _inherit = "pos.order.line"

    commission_policy_line_image_ids = fields.Many2many(
        "commission.policy.line.image", string="Policy Line Images", index=True, copy=False
    )
    pricelist_item_id = fields.Many2one("product.pricelist.item")

    @api.model
    def get_commission_policy_line_image(self, days):
        for line in self.commission_policy_line_image_ids:
            if line.date_from <= days <= line.date_to:
                return line
            if line.infinite and line.date_from <= days:
                return line
        return False
