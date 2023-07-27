import logging
from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ResPartnerInherit(models.Model):
    _inherit = "res.partner"

    seller_id = fields.Many2one(
        "hr.employee",
        string="Seller",
        tracking=True,
        help="Seller associated with the partner.",
    )

    @api.model
    def _commercial_fields(self):
        """Returns the list of fields that are managed by the commercial entity
        to which a partner belongs. These fields are meant to be hidden on
        partners that aren't `commercial entities` themselves, and will be
        delegated to the parent `commercial entity`. The list is meant to be
        extended by inheriting classes."""

        res = super()._commercial_fields()
        res.append("seller_id")

        return res
