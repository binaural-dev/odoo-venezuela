from odoo import api, fields, models, _
from odoo.exceptions import UserError

class PosPaymentMethod(models.Model):
    _inherit = "pos.payment.method"

    payment_name_in_mf = fields.Char()