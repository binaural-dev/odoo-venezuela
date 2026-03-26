from odoo import api, fields, models,  Command, _
from odoo.tools.sql import column_exists, create_column
from odoo.tools import  float_compare, formatLang
from odoo.exceptions import UserError

import logging
_logger = logging.getLogger(__name__)



class AccountAccount(models.Model):
    _inherit = "account.account"

    is_advance_account = fields.Boolean('¿is advance account?', default=False, help="Account used for advance payment")

    @api.onchange('is_advance_account', 'account_type')
    def _onchange_is_advance_account(self):
        for rec in self:
            if rec.is_advance_account and rec.account_type:
                if rec.account_type not in ['asset_current', 'liability_current']:
                    raise UserError(_(
                        "An account flagged for advances must be of type "
                        "'Current Assets' or 'Current Liabilities'."
                    ))