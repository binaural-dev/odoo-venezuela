from odoo import fields, models
from odoo.http import request


class Website(models.Model):
    _inherit = "website"

    do_not_show_products_without_availability_on_site = fields.Boolean(default=False)

    # def _search_with_fuzzy(self, search_type, search, limit, order, options):
    #     res = super()._search_with_fuzzy(search_type, search, limit, order, options)
    #     for result in res[1]:
    #         if result["model"] == "product.template":
    #             products = result["results"]
    #             company_id = request.env.user.company_id
    #             products_filtered = products.filtered(lambda p: p.company_id in company_id)
    #             result["results"] = products_filtered
    #             result["count"] = len(products_filtered)
    #     return res
