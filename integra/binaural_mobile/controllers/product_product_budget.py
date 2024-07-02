import hashlib
import json
import logging

from odoo import _, http
from odoo.http import request
from odoo.osv import expression
from werkzeug import urls

from . import utils

_logger = logging.getLogger(__name__)
FIELDNAMES = [
    "id",
    "name",
    "type",
    "display_name",
    "qty_available",
    "quantity",
    "list_price",
    "default_code",
    "barcode",
    "brand_id",
    "taxes_id",
    "packaged_product",
    "packaging_ids",
    "uom_id",
    "type",
    "product_template_attribute_value_ids",
]
VARIANT_TAG_FIELDS = ["id", "name"]
FIELDFILTERS = ["id", "search_name", "brand_id", "available_qty", "quantity",]
FIELDITEMS = ["id", "product_tmpl_id", "pricelist_id", "fixed_price", "min_quantity", "compute_price", "applied_on"]


class ProductProductBudget(http.Controller):
    
    def _filter_product_packaging_id(self, package_id, dict_product_id):
        if package_id.id not in dict_product_id["packaging_ids"]:
            return False

        return True


    def _get_products_with_packaging(self, dict_product_ids, product_ids):
        packaging_ids = product_ids.mapped("packaging_ids")

        filtered_dict_product_ids = []

        for dict_product_id in dict_product_ids:
            current_packaging_ids = packaging_ids.filtered(lambda pack_id: self._filter_product_packaging_id(pack_id, dict_product_id))
            # qty_available = dict_product_id["qty_available"]

            # if current_packaging_ids and not allow_out_of_stock_order:
            #     default_packaging_id = current_packaging_ids[0]

            #     if qty_available < default_packaging_id.qty:
            #         continue

            dict_packaging_ids = current_packaging_ids.read(["id", "name", "qty", "product_uom_id", "sales", "purchase"])
            dict_product_id["packaging_ids"] = dict_packaging_ids
            
            filtered_dict_product_ids.append(dict_product_id)

        return filtered_dict_product_ids

    @http.route(
        '/budget/product', type="json", auth="public", website=False, sitemap=False
    )
    def get_product_product(self, fee=False, limit=0, offset=0, uid=False, **kw):
        """
        This function is used to consult the products that are available 
        when creating the quote by the seller, it consults the types of
          products that are available due to the configuration

        Args:
            fee (int, ): is the rate selected by the seller. Defaults to False.

        Returns:
            dic: product search results
        """
        data = {"status": 200, "msg": _("Success")}
        name_search = kw.get("product")
        company_id = request.env.user.company_id
        
        product_type = [('consu', company_id.product_type_consu),
                ('service', company_id.product_type_service),
                ('product', company_id.product_type_product)]

        product_type = [ptype[0] for ptype in filter(lambda x: x[1], product_type)]

        domain = [
            ("active", "=", True), 
            ("sale_ok", "=", True), 
            ("type", "in", product_type),
            ]
        
        res_company = request.env["res.company"].sudo().search([])
        allow_out_of_stock_order = request.env['res.config.settings'].sudo().get_values().get('allow_out_of_stock_order')
        
        if len(res_company) > 1:
            domain = expression.AND([domain, [("company_id", "=", company_id.id)]])
        
        if name_search:
            search = utils.search_name("product.product", name_search, domain)
            ids = [product[0] for product in search]
            domain = [("id", "in", ids)]

        record_product_ids = utils.search_model_data(
            "product.product", domain, int(limit), int(offset), order="name asc, quantity desc"
        )
        product_ids = record_product_ids.read(FIELDNAMES)

        product_ids = self.get_variant_tags(product_ids)
        result = list()

        if 'product' in product_type:
            product_product = product_ids.copy()
            product_consu_service = product_ids.copy()
            if not allow_out_of_stock_order:
                product_product = list(filter(lambda product: (product.get('type') == "product" and product.get('quantity') > 0) , product_ids))
            product_consu_service = list(filter(lambda product: product.get('type') in ['consu', 'service'], product_ids))

            if len(product_product) > 0:
                result.append(product_product)

            if len(product_consu_service)> 0:
                result.append(product_consu_service)

            product_ids = result

        products_without_pricelist = []

        type_mapping = {
            "service": _("Service"),
            "consu": _("Consumable"),
            "product": "product"
        }

        products_without_pricelist = []
        for product_id in product_ids:
            for product in product_id:
                product["msg_price"] = False
                product_type = type_mapping.get(product["type"], product["type"])
                product["type"] = product_type
                products_without_pricelist.append(product["id"])

        domain_price = [("product_tmpl_id", "in", products_without_pricelist), ("pricelist_id", "=", fee)]

        if len(res_company) > 1:
            domain_price = expression.AND([domain_price, [("company_id", "=", company_id.id)]])

        products_pricelist_ids = request.env["product.pricelist.item"].search_read(domain_price, FIELDITEMS)
        company_user = request.env.company
        for product_id in product_ids:
            for product in product_id:
                for product_price in products_pricelist_ids:
                    if product_price['product_tmpl_id'][0] == product['id']:
                        product["msg_price"] = _("Different price/s due to rate conditions")

        all_product_count = utils.get_model_count("product.product", domain)
        product_count = len(product_ids)
        if not product_count:
            data.update(
                {"status": 204, "msg": _("No products available"), "count": 0, "data": False}
            )
            return json.dumps(data)

        dict_product_ids = self.get_url_image_product(result)

        dict_product_ids = self._get_products_with_packaging(dict_product_ids, record_product_ids)

        data.update({
            "data": dict_product_ids, 
            "count": len(dict_product_ids), 
            "total_count": all_product_count,
            "stock_packaging": company_user.group_stock_packaging,
            "allow_out_of_stock_order": allow_out_of_stock_order,
        })

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
            for value in product:
                rec = utils.browse_model_data("product.product", value.get("id"))
                sha = hashlib.sha512(str(getattr(rec, "__last_update")).encode("utf-8")).hexdigest()[:7]
                product_cpy = value.copy()
                product_id = str(value.get("id"))
                url_img = f"/web/image/product.product/{product_id}/image_1024?unique={sha}"
                url_complete = urls.url_join(url, url_img)
                product_cpy.update({"image": url_complete})
                products.append(product_cpy)

        return products