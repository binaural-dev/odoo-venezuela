import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    def packaging_one_validate(self):
        use_multiple_packaging = self.env.company.use_multiple_packaging
        
        if not use_multiple_packaging:
            super().packaging_one_validate()

        for product in self:
            if product.packaged_product and len(product.packaging_ids) == 0:
                raise UserError(_("To validate in the Sales App by packaging, at least one or more packaging per product must be specified"))
