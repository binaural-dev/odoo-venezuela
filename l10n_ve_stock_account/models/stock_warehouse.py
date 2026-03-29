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

    is_donation_warehouse = fields.Boolean(
        string="Donation Warehouse",
        default=False,
        help="Indicates if this warehouse is used for donation purposes.",
    )

    readonly_is_donation_warehouse = fields.Boolean(
        string="Readonly Donation Warehouse",
        compute="_compute_readonly_is_donation_warehouse",
    )

    ### COMPUTES ###
    def _compute_readonly_is_consignation_warehouse(self):
        for warehouse in self:
            warehouse.readonly_is_consignation_warehouse = warehouse.is_consignation_warehouse

    def _compute_readonly_is_donation_warehouse(self):
        for warehouse in self:
            warehouse.readonly_is_donation_warehouse = warehouse.is_donation_warehouse

    ### CONSTRAINTS ###

    @api.constrains("is_consignation_warehouse")
    def _check_unique_consignation_warehouse(self):
        for warehouse in self:
            if warehouse.is_consignation_warehouse and self.search_count(
                [
                    ("is_consignation_warehouse", "=", True),
                    ("id", "!=", warehouse.id),
                ]
            ) > 0:
                raise ValidationError(_("There can only be one consignation warehouse."))

    @api.constrains("is_donation_warehouse")
    def _check_unique_donation_warehouse(self):
        for warehouse in self:
            if warehouse.is_donation_warehouse and self.search_count(
                [
                    ("is_donation_warehouse", "=", True),
                    ("id", "!=", warehouse.id),
                ]
            ) > 0:
                raise ValidationError(_("There can only be one donation warehouse."))
