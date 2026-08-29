from odoo import api, models
from odoo.fields import Domain


class ProductProduct(models.Model):
    _inherit = "product.product"

    @api.model
    def name_search(self, name="", domain=None, operator="ilike", limit=100):
        results = super().name_search(name, domain, operator, limit)
        if not name or operator in Domain.NEGATIVE_OPERATORS:
            return results
        remaining_limit = None
        if limit:
            remaining_limit = limit - len(results)
            if remaining_limit <= 0:
                return results
        alternate_domain = Domain(domain or Domain.TRUE) & Domain(
            "alternate_code", operator, name
        )
        if results:
            alternate_domain &= Domain("id", "not in", [res[0] for res in results])
        products = self.search_fetch(
            alternate_domain, ["display_name"], limit=remaining_limit
        )
        return results + [
            (product.id, product.display_name) for product in products
        ]
