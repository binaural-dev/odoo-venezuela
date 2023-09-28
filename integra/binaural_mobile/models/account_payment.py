from odoo import api, fields, models, Command
from odoo.tools.float_utils import float_round


class AccountPayment(models.Model):
    _inherit = "account.payment"

    payment_from_app = fields.Boolean(default=False, tracking=True)