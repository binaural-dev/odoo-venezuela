from odoo import fields, models


class PaymentMethod(models.Model):
    _name = 'payment.method.tfhka'
    _description = 'TFHKA payment methods'
    _rec_name = 'code'
    _order = 'code'

    code = fields.Char(
        size=2,
        help="This code identifies the payment method. It is used to digitize and link the "
        "corresponding payment method.",
        required=True,
        copy=False,
    )
    description = fields.Char(size=100, required=True)

    _code_uniq = models.Constraint(
        "unique(code)",
        "The payment method code already exists",
    )
