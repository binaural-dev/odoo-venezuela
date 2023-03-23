from odoo import models, fields, api, _


class PosPaymentMethod(models.Model):
    _inherit = "pos.payment.method"

    is_foreign_currency = fields.Boolean(default=False)
