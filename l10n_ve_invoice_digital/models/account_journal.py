from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AccountJournal(models.Model):
    _inherit = "account.journal"

    payment_method_code = fields.Many2one(
        "payment.method.tfhka",
        help="This code identifies the payment method. It is used to digitize and link the corresponding payment method.")
