from odoo import api, models


class ProductPricelistReport(models.AbstractModel):
    _inherit = "report.product.report_pricelist"

    @api.model
    def _get_report_data(self, data, report_type="html"):
        """Reuse the core single-pricelist report for the product/variant
        structure, then replace its single 'price' per product with a
        'prices' dict keyed by pricelist id for every selected pricelist.

        `page`/`page_size` (only sent by the on-screen HTML preview, never
        by the PDF export) restrict how many of the requested `active_ids`
        are actually resolved and priced in this call, so a large product
        selection doesn't have to be computed all at once just to show one
        page of it.
        """
        pricelist_ids = data.get("pricelist_ids") or []
        pricelists = self.env["product.pricelist"].browse(pricelist_ids).exists()

        active_ids = data.get("active_ids") or []
        page_size = data.get("page_size")
        if page_size and active_ids:
            page = max(1, data.get("page") or 1)
            start = (page - 1) * page_size
            active_ids = active_ids[start:start + page_size]

        res = super()._get_report_data(
            dict(data, active_ids=active_ids, pricelist_id=pricelists[:1].id, quantities=[1]),
            report_type,
        )

        product_model = "product.template" if res["is_product_tmpl"] else "product.product"
        self._set_pricelist_prices(res["products"], pricelists, product_model)

        res["pricelists"] = pricelists
        res.pop("pricelist", None)
        res.pop("quantities", None)
        return res

    def _set_pricelist_prices(self, products_data, pricelists, product_model):
        """Compute each pricelist's price for the whole `products_data` batch
        in one call per pricelist (via `_get_products_price`), instead of
        once per (product, pricelist) pair — the difference between O(m)
        and O(n*m) database round-trips for n products and m pricelists.
        """
        if not products_data:
            return

        products = self.env[product_model].browse([p["id"] for p in products_data])
        prices_by_pricelist = {
            pricelist.id: pricelist._get_products_price(products, 1) for pricelist in pricelists
        }

        variants_data = []
        for product_data in products_data:
            product_data["prices"] = {
                pricelist_id: prices.get(product_data["id"], 0.0)
                for pricelist_id, prices in prices_by_pricelist.items()
            }
            product_data.pop("price", None)
            variants_data.extend(product_data.get("variants") or [])

        if variants_data:
            self._set_pricelist_prices(variants_data, pricelists, "product.product")
