from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ProductCategory(models.Model):
    _inherit = "product.category"

    @api.onchange("property_stock_valuation_account_id")
    def _onchange_property_stock_valuation_account_id(self):

        if self.env.company.use_same_account_stock_valuation_to_category:
            raise ValidationError(
                _(
                    "It is not allowed to change this category due to the division method used in landed costs."
                )
            )
