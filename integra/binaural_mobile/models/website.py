from odoo import api, fields, models, _
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)
class WebsiteInh(models.Model):
    _inherit = "website"

    def _search_with_fuzzy(self, search_type, search, limit, order, options):
        """
        This function is used in different types of searches that have to do 
        with products in Odoo, so if the user doing the search is a seller, 
        it will filter the results of the products to be displayed by the 
        types of products that the seller can search for. system configuration

        Returns:
            Tuple: Products filtered results
        """
        res = super()._search_with_fuzzy(search_type, search, limit, order, options)
        if request.env.user.employee_id.is_seller:
            for result in res[1]:
                if result["model"] == "product.template":
                    products = result["results"]
                    company_id = request.env.user.company_id
                    product_type = [
                        ("consu", company_id.product_type_consu),
                        ("service", company_id.product_type_service),
                        ("product", company_id.product_type_product),
                    ]
                    product_type = [ptype[0] for ptype in filter(lambda x: x[1], product_type)]
                    products_filtered = products.filtered(lambda p: p.detailed_type in product_type)
                    result["results"] = products_filtered
                    result["count"] = len(products_filtered)
        return res
