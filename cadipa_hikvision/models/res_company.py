from odoo import models, fields
import logging

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):
    _inherit = "res.company"

    cadipa_waiting_message = fields.Char(
        string="Default Waiting Message",
        default="Esperando...",
        help="Default message to display on the waiting screen.",
    )

    cadipa_waiting_color = fields.Char(
        string="Default Waiting Color",
        default="#2c3e50",
        help="Default background color for the waiting screen (hexadecimal format, e.g. #2c3e50).",
    )

    cadipa_overdue_limit = fields.Integer(
        string="Overdue Entries Limit",
        default=0,
        help="Limit of overdue entries allowed before showing warning message.",
    )
