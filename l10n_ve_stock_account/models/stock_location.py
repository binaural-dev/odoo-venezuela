from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

import logging

_logger = logging.getLogger(__name__)


class StockLocation(models.Model):
    _inherit = "stock.location"

    partner_id = fields.Many2one(
        "res.partner",
        string="Assigned Customer",
        help="This location is assigned to a specific customer for consignation.",
    )

    is_consignation_warehouse = fields.Boolean(
        string="Consignation Warehouse",
        compute="_compute_is_consignation_warehouse",
        store=True,
    )

    @api.constrains("usage", "location_id")
    def _check_internal_location_only(self):
        for record in self:
            warehouse = record.get_warehouse()
            if warehouse and warehouse.is_consignation_warehouse and record.usage != "internal":
                raise ValidationError(
                    _("Only 'Internal' locations can be created inside a consignation warehouse.")
                )

    @api.depends("location_id")
    def _compute_is_consignation_warehouse(self):
        for record in self:
            warehouse = record.get_warehouse()
            record.is_consignation_warehouse = bool(
                warehouse and warehouse.is_consignation_warehouse
            )

    def get_warehouse(self):
        if not self.id:
            return False

        warehouse = self.env["stock.warehouse"].search(
            [
                "|",
                ("lot_stock_id", "=", self.id),
                ("view_location_id", "parent_of", self.id),
            ],
            limit=1,
        )
        return warehouse
