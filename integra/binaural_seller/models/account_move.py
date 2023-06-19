from odoo import fields, models

import logging

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    seller_id = fields.Many2one(
        "hr.employee",
        string="Seller",
        tracking=True,
        store=True,
        related='partner_id.seller_id',
        help="Partner's seller reference."
    )
