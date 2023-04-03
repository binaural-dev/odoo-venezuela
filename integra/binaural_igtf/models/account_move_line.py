from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AccountMoveLineIgtf(models.Model):
    _inherit = "account.move.line"

   