import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.http import request

_logger = logging.getLogger(__name__)
class ProductTemplate(models.Model):
    _inherit = 'product.template'

    packaged_product = fields.Boolean(default=False, help="Sale of product by packaging")

    @api.model_create_multi
    def create(self, vals_list):
        product = super().create(vals_list)
        product.packaging_one_validate()
        return product

    def write(self, vals):
        res = super().write(vals)
        if "packaged_product" in vals or "packaging_ids" in vals:
            for product in self:
                product.packaging_one_validate()
        return res

    def packaging_one_validate(self):
        for product in self:
            if product.packaged_product and (len(product.packaging_ids) == 0 or len(product.packaging_ids) >= 2):
                raise UserError(_("To validate in the Sales App by packaging, only one packaging per product is allowed"))

    def _search_get_detail(self, website, order, options):
        res = super()._search_get_detail(website, order, options)
        search_fields = res.get('search_fields')
        search_fields.append('brand_id.name')
        if request.env.user.employee_id.is_seller:
            search_fields.append('alternate_code')
        res.update({'search_fields': search_fields})
        return res
    
