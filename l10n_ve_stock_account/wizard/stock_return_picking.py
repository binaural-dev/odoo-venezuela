import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.fields import Domain
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)

from odoo.exceptions import UserError


class StockReturnInvoicePicking(models.TransientModel):
    _inherit = "stock.return.picking"

    def _create_return(self):
        """in this function the picking is marked as return"""

        new_picking = super(StockReturnInvoicePicking, self)._create_return()
        new_picking.write({"is_return": True})
        return new_picking
