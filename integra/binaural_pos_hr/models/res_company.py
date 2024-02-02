from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    pos_discount_require_supervisor_key = fields.Boolean("Supervisor Key Discounts")
    pos_refund_require_supervisor_key = fields.Boolean("Supervisor Key Refunds")
