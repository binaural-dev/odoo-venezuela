from odoo import models, _
from odoo.exceptions import UserError


class AccountMoveLineInh(models.Model):
    _inherit = "account.move.line"
