from odoo import api, fields, models
import logging

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    date_end = fields.Date(
        string="deadline end of installment amount",
        help="deadline end of installment amount",
        related="company_id.date_end",
        readonly=False,
    )

    deadline_amount = fields.Float(
        "Deadline Amount", related="company_id.deadline_amount", readonly=False, default=0
    )
