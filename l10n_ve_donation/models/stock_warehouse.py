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

    @api.constrains("is_donation_warehouse", "company_id")
    def _check_unique_donation_warehouse(self):
        for record in self:
            if not record.is_donation_warehouse:
                continue
            
            domain = [
                ("id", "!=", record.id),
                ("is_donation_warehouse", "=", True),
                ("company_id", "=", record.company_id.id),
            ]
            
            if "subsidiary_id" in record._fields:
                domain.append(("subsidiary_id", "=", record.subsidiary_id.id))
            
            if self.search_count(domain) > 0:
                raise ValidationError(_("There can only be one donation warehouse per company/subsidiary."))
