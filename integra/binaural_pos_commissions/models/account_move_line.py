from odoo import fields, models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def get_commission(self, collection_days):
        res = super().get_commission(collection_days)
        if self.pos_order_line_ids:
            return self.pos_order_line_ids.get_commission_policy_line_image(collection_days)
        return res


