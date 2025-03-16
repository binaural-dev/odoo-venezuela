from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

import logging

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    guide_number = fields.Char(related="picking_id.guide_number")
    picking_id = fields.Many2one("stock.picking", string="Picking")
    transfer_ids = fields.Many2many("stock.picking", string="Transfers")
    
