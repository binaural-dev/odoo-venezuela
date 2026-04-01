from odoo import models, fields, api

class StockLocation(models.Model):
    _inherit = "stock.location"

    is_donation_warehouse = fields.Boolean(
        string="Donation Warehouse",
        compute="_compute_is_donation_warehouse",
        store=True,
    )

    @api.depends("location_id")
    def _compute_is_donation_warehouse(self):
        for record in self:
            warehouse = record.get_warehouse() if hasattr(record, 'get_warehouse') else False
            record.is_donation_warehouse = bool(
                warehouse and hasattr(warehouse, 'is_donation_warehouse') and warehouse.is_donation_warehouse
            )
