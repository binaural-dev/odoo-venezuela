from odoo import models, fields
import logging

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    cadipa_waiting_message = fields.Char(
        related="company_id.cadipa_waiting_message",
        readonly=False,
        help="Default message to display on the waiting screen.",
    )

    cadipa_waiting_color = fields.Char(
        related="company_id.cadipa_waiting_color",
        readonly=False,
        help="Default background color for the waiting screen (hexadecimal format, e.g. #2c3e50).",
    )

    cadipa_overdue_limit = fields.Integer(
        related="company_id.cadipa_overdue_limit",
        readonly=False,
        help="Limit of overdue entries allowed before showing warning message.",
    )
