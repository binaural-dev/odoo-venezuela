from odoo import fields, models, api
import logging

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):
    _inherit = "res.company"

    tax_period = fields.Selection(
        [
            ("fortnightly", "Fortnightly"),
            ("monthly", "Monthly"),
        ],
        string="Tax Period",
    )

    lock_date_tax_validation = fields.Boolean(
        string="Validation to Block Invoice Creation",
    )
