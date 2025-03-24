from odoo import fields, models, api, _


class PosPaymentMethod(models.Model):
    _inherit = "pos.payment.method"

    code_fiscal_printer = fields.Char(size=2, default="01")
