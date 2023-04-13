import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class AccountJournal(models.Model):
    _inherit = "account.journal"

    series_correlative_sequence_id = fields.Many2one(
        "ir.sequence", string="Series control number", tracking=True
    )