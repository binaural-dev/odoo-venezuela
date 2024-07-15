from odoo import fields, models, _


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    commission_amount = fields.Float()
    collection_days = fields.Integer(related="move_id.collection_days")
    commission_image_id = fields.Many2one("commission.policy.line.image", string="Commission Image")
    policy_type_id = fields.Many2one(related="commission_image_id.policy_type_id")
    policy_type_name = fields.Selection(related="policy_type_id.policy_type")
    policy_type = fields.Selection(related="commission_image_id.policy_type")

    def get_commission(self, collection_days):
        commission_id = self.env["commission.policy.line.image"]
        if self.sale_line_ids:
            commission_id = self.sale_line_ids.get_commission_policy_line_image(collection_days)
        return commission_id
