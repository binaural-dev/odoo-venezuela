from odoo import models, fields


class ProductTemplate(models.Model):
    _inherit = "product.template"

    commission_policy_id = fields.Many2one("commission.policy", string="Commission")
