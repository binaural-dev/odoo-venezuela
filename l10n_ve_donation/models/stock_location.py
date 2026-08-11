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
            warehouse = record.get_warehouse()
            record.is_donation_warehouse = bool(
                warehouse and warehouse.is_donation_warehouse
            )

    def get_warehouse(self):
        """Return the warehouse associated with this stock location, or False if none found."""
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
