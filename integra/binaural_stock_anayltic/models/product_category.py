from odoo import api, models


class ProductCategory(models.Model):
    _inherit = "product.category"

    @api.model
    def is_analytic_category(self):
        self.ensure_one()
        property_cost_method = "average"
        property_valuation = "real_time"

        return self.property_cost_method == property_cost_method and self.property_valuation == property_valuation
