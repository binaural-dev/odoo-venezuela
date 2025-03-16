from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError

import logging

_logger = logging.getLogger(__name__)


class StockLocation(models.Model):
    _inherit = "stock.location"

    partner_id = fields.Many2one(
        "res.partner",
        string="Assigned Customer",
        help="This location is assigned to a specific customer for consignation.",
        required=True,
    )

    @api.constrains("partner_id", "location_id")
    def _check_consignation_location(self):
        for record in self:
            if (
                record.location_id
                and record.location_id.is_consignation_warehouse
                and not record.partner_id
            ):
                raise ValidationError(_("Consignation locations must be linked to a customer."))
