from odoo import api, fields, models, Command, _
from odoo.tools import float_compare
from odoo.exceptions import UserError
from datetime import date, timedelta
import traceback

import logging

_logger = logging.getLogger(__name__)


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"
    
    account_analytic_id = fields.Many2one(related="move_id.account_analytic_id", string="Analytic Account")