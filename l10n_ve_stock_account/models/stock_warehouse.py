from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class StockWarehouse(models.Model):
    _inherit = "stock.warehouse"

    is_consignation_warehouse = fields.Boolean(
        string="Consignation Warehouse",
        default=False,
        help="Indicates if this warehouse is used for consignation purposes.",
    )

    readonly_is_consignation_warehouse = fields.Boolean(
        string="Readonly Consignation Warehouse",
        compute="_compute_readonly_is_consignation_warehouse",
    )

    ### COMPUTES ###
    def _compute_readonly_is_consignation_warehouse(self):
        for warehouse in self:
            warehouse.readonly_is_consignation_warehouse = warehouse.is_consignation_warehouse

    ### CONSTRAINTS ###

    @api.constrains("is_consignation_warehouse")
    def _check_unique_consignation_warehouse(self):
        if (
            self.is_consignation_warehouse
            and self.search_count([("is_consignation_warehouse", "=", True)]) > 1
        ):
            raise ValidationError(_("There can only be one consignation warehouse."))
