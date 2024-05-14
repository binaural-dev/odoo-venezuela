from odoo import fields, models, _, api
from odoo.osv import expression

import logging

_logger = logging.getLogger(__name__)


class AccountJournal(models.Model):
    _inherit = "account.journal"

