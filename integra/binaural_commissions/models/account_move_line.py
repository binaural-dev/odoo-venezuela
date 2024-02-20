from odoo import fields, models, _


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    commission_amount = fields.Float()
    collection_days = fields.Integer(related="move_id.collection_days")
    commission_image_id = fields.Many2one("commission.policy.line.image", string="Commission Image")
    policy_type = fields.Selection(related="commission_image_id.policy_type")
