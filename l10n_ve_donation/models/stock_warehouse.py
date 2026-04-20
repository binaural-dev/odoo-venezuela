from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class StockWarehouse(models.Model):
    _inherit = "stock.warehouse"

    is_donation_warehouse = fields.Boolean(
        string="Donation Warehouse",
        default=False,
        help="Indicates if this warehouse is used for donation purposes.",
    )

    readonly_is_donation_warehouse = fields.Boolean(
        string="Readonly Donation Warehouse",
        compute="_compute_readonly_is_donation_warehouse",
    )

    def _compute_readonly_is_donation_warehouse(self):
        for warehouse in self:
            warehouse.readonly_is_donation_warehouse = warehouse.is_donation_warehouse

    @api.constrains("is_donation_warehouse")
    def _check_unique_donation_warehouse(self):
        if (
            self.is_donation_warehouse
            and self.search_count([("is_donation_warehouse", "=", True)]) > 1
        ):
            raise ValidationError(_("There can only be one donation warehouse."))
