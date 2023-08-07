from odoo import _, api, models
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = "product.template"

    @api.constrains("supplier_taxes_id")
    def _check_taxes_id(self):
        for product in self:
            if len(product.supplier_taxes_id) != 1 and self.env.company.unique_tax:
                raise ValidationError(_("This product must have only one tax on purchase."))
