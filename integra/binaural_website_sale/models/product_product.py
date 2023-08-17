from odoo import models


class Product(models.Model):
    _inherit = "product.product"

    def get_available_quantity_by_warehouse(self, warehouse_id):
        """
        Returns the available quantity of the product on the given warehouse.

        Parameters
        ----------
        warehouse_id : stock.warehouse
            The warehouse in which locations are gonna be checked the availablity of the product.

        Returns
        -------
        int
            The available quantity of the product on the given warehouse.
        """
        self.ensure_one()
        Quant = self.env["stock.quant"]
        available_quantity = Quant._get_available_quantity(self, warehouse_id.view_location_id)
        return available_quantity
