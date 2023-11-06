from odoo import api, fields, models
import logging

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.Model):
    _inherit = "res.company"

    date_end = fields.Date(
        string="deadline end of installment amount",
        help="deadline end of installment amount"
    )

    deadline_amount = fields.Float("Deadline Amount")

    