from odoo import fields, models
from odoo.http import request


class Website(models.Model):
    _inherit = "website"

    do_not_show_products_without_availability_on_site = fields.Boolean(default=False)

    def _search_with_fuzzy(self, search_type, search, limit, order, options):
        res = super()._search_with_fuzzy(search_type, search, limit, order, options)
        company_count = request.env["res.company"].sudo().search_count([])        
        if company_count > 1:
            for result in res[1]:
                if result["model"] == "product.template":
                    products = result["results"]
                    website = request.env['website'].get_current_website()
                    products_filtered = products.filtered(
                        lambda p: p.company_id.id == website._get_cached('company_id')
                    )
                    result["results"] = products_filtered
                    result["count"] = len(products_filtered)
        return res
