import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = "stock.picking"

    analytic_account_id = fields.Many2one("account.analytic.account")
