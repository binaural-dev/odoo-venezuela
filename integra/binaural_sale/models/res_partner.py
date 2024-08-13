from odoo import models, fields, api, _
from odoo.exceptions import MissingError

import logging

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = "res.partner"

    use_partner_credit_limit_order = fields.Boolean(
        string="Partner Order Limit",
        groups="account.group_account_invoice,account.group_account_readonly",
    )