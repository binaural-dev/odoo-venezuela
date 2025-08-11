from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class SaleSubscriptionPlan(models.Model):
    _inherit = 'sale.subscription.plan'

    initial_fee_product = fields.Many2one("product.template")
    activation_initial_percentage = fields.Integer()