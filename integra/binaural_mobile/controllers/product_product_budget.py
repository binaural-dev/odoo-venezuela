import logging
import hashlib
import json

from odoo import _, http
from odoo.http import request
from odoo.osv import expression
from werkzeug import urls
from . import utils

_logger = logging.getLogger(__name__)
FIELDNAMES = [
    "id",
    "name",
    "display_name",
    "qty_available",
    "list_price",
    "default_code",
    "barcode",
    "brand_id",
    "taxes_id",
    # "sales_policy",
    # "available_qty",
    "product_template_attribute_value_ids",
]
VARIANT_TAG_FIELDS = ["id", "name"]
FIELDFILTERS = ["id", "search_name", "brand_id", "available_qty"]


class ProductProductBudget(http.Controller):
    @http.route(
        '/budget/product', type="json", auth="public", website=False, sitemap=False
    )
    def get_product_product(self, limit=0, offset=0, uid=False, **kw):
        data = {"status": 200, "msg": _("Success")}
        name_search = kw.get("product")
        company_id = request.env.user.company_id.id
        domain = [
            ("active", "=", True), 
            ("sale_ok", "=", True), 
            ("type", "=", "product"), 
            ]
        
        res_company = request.env["res.company"].sudo().search([])
        if len(res_company) > 1:
            domain = expression.AND([domain, [("company_id", "=", company_id)]])
        
        if name_search:
            search = utils.search_name("product.product", name_search, domain)
            ids = [product[0] for product in search]
            domain = [("id", "in", ids)]

        product_ids = utils.get_model_data(
            "product.product", domain, FIELDNAMES, int(limit), int(offset)
        )
        product_ids = self.get_variant_tags(product_ids)
        all_product_count = utils.get_model_count("product.product", domain)
        product_count = len(product_ids)
        if not product_count:
            data.update(
                {"status": 204, "msg": _("No products available"), "count": 0, "data": False}
            )
            return json.dumps(data)

        product_ids = self.get_url_image_product(product_ids)
        data.update({"data": product_ids, "count": product_count, "total_count": all_product_count})

        return json.dumps(data)

    def get_variant_tags(self, product_ids):
        products = []
        for product in product_ids:
            product_cpy = product.copy()
            domain = [("id", "in", product_cpy.get("product_template_attribute_value_ids"))]
            tags = utils.get_model_data(
                "product.template.attribute.value", domain, VARIANT_TAG_FIELDS
            )
            product_cpy.update({"product_template_attribute_value_ids": tags})
            products.append(product_cpy)

        return products

    def get_url_image_product(self, product_ids):
        """Concat the image URL of every product

        Parameters
        ----------
        product_ids
            a list of products

        Returns
        -------
            The products with their respective image url.
        """

        url = request.env["ir.config_parameter"].sudo().get_param("web.base.url")
        products = []
        for product in product_ids:
            rec = utils.browse_model_data("product.product", product.get("id"))
            sha = hashlib.sha512(str(getattr(rec, "__last_update")).encode("utf-8")).hexdigest()[:7]
            product_cpy = product.copy()
            product_id = str(product.get("id"))
            url_img = f"/web/image/product.product/{product_id}/image_1024?unique={sha}"
            url_complete = urls.url_join(url, url_img)
            product_cpy.update({"image": url_complete})
            products.append(product_cpy)

        return products


# filters = ["name"]
# search_by_attribute = [["product_template_attribute_value_ids.name", "in", kwargs.get(FIELDFILTERS[1])]]
# search_domains = [utils.get_search_domain(filterKey, kwargs.get(FIELDFILTERS[1])) for filterKey in filters]
# search_domains = expression.OR(search_domains)
# domain = expression.AND([domain, search_domains])
