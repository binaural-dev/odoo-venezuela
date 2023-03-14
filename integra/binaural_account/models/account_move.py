import logging
from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    correlative = fields.Char("Control Number", copy=False, help="Sequence control number")
    invoice_reception_date = fields.Date("Reception Date", help="Indicates when the invoice was received by the client/company")