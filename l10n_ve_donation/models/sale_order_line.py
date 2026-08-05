from odoo import models

class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def _action_launch_stock_rule(self, previous_product_uom_qty=False):
        """
        Override to force the procurement destination location to the standard customer location
        when the sale order is a donation. Since the partner of a donation is the company itself,
        its default customer location might be an internal transit location, which breaks routes.
        """
        res = super()._action_launch_stock_rule(previous_product_uom_qty=previous_product_uom_qty)
        return res
