from odoo import models, fields, api
from odoo.http import request

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    def _search_get_detail(self, website, order, options):
        res = super()._search_get_detail(website, order, options)
        search_fields = res.get('search_fields')
        search_fields.append('brand_id.name')
        if request.env.user.employee_id.is_seller:
            search_fields.append('alternate_code')
        res.update({'search_fields': search_fields})
        return res