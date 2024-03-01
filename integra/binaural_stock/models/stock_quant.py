from odoo import fields, models

import logging

_logger = logging.getLogger(__name__)


class StockQuan(models.Model):
    _inherit = "stock.quant"

