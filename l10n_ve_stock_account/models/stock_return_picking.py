import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.osv import expression
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)

from odoo.exceptions import UserError


class StockReturnInvoicePicking(models.TransientModel):
    _inherit = "stock.return.picking"

    def _create_returns(self):
        """in this function the picking is marked as return"""

        new_picking, pick_type_id = super(StockReturnInvoicePicking, self)._create_returns()
        picking = self.env["stock.picking"].browse(new_picking)
        picking.write({"is_return": True})
        return new_picking, pick_type_id
