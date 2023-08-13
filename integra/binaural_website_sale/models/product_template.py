from odoo.http import request
from odoo import models, api
from odoo.osv import expression


class ProductTemplate(models.Model):
    _inherit = "product.template"

    @api.model
    def _search_get_detail(self, website, order, options):
        res = super()._search_get_detail(website, order, options)
        return res | {"requires_sudo": True}

    @api.model
    def _search_build_domain(self, domain, search, fields, extra=None):
        res = super()._search_build_domain(domain, search, fields, extra=extra)
        if not request.website.sudo().do_not_show_products_without_availability_on_site:
            return res

        qty_available_domain = [
            ("qty_available", ">", 0),
            ("company_id", "in", (self.env.company.id, False)),
        ]
        return expression.AND([qty_available_domain, res])

    @api.model
    def _search_fetch(self, search_detail, search, limit, order):
        """
        Filters the result of the original _search_fetch method and returns just the products that
        have available quantity on any location of the website's warehouse.
        """
        results, count = super()._search_fetch(search_detail, search, limit, order)
        if not request.website.sudo().do_not_show_products_without_availability_on_site:
            return results, count

        WAREHOUSE_ID = request.website.sudo().warehouse_id
        def is_available_quantity_greater_than_zero_on_warehouse(product):
            return (
                sum(
                    variant.get_available_quantity_by_warehouse(WAREHOUSE_ID)
                    for variant in product.product_variant_ids
                )
                > 0
            )

        products_with_available_quantity = results.filtered(
            is_available_quantity_greater_than_zero_on_warehouse
        )
        return products_with_available_quantity, len(products_with_available_quantity)
