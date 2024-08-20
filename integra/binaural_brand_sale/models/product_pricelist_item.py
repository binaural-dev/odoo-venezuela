from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ProductPricelistItem(models.Model):
    _inherit = "product.pricelist.item"

    applied_on = fields.Selection(
        selection_add=[("3_global",), ("brand", "Brand")],
        ondelete={"brand": "set default"},
    )

    brand_id = fields.Many2one(
        "product.brand",
        string="Brand to product",
        ondelete="cascade",
        help="Trademarks related to the product",
        store=True,
    )

    # ====== COMPUTE METHODS =======#

    @api.depends("price")
    def _compute_prices_with_tax(self):
        for item in self:
            if not item.product_tmpl_id.taxes_id or not item.product_tmpl_id:
                item.price_without_tax = item.fixed_price
                item.price_with_tax = item.fixed_price
                continue
            taxes = item.product_tmpl_id.taxes_id.compute_all(
                item.fixed_price, item.currency_id, 1, product=item.product_tmpl_id
            )
            item.price_without_tax = taxes["total_excluded"]
            item.price_with_tax = taxes["total_included"]

    @api.depends("brand_id", "applied_on")
    def _compute_name_and_price(self):
        super()._compute_name_and_price()
        for item in self:
            if item.brand_id and item.applied_on == "brand":
                item.name = _("Brands: %s") % (item.brand_id.name)

    # ====== CONSTRAINT METHODS =======#

    @api.constrains("brand_id")
    def _check_product_consistency(self):
        super()._check_product_consistency()
        for item in self:
            if item.applied_on == "brand" and not item.brand_id:
                raise ValidationError(
                    _("Please specify the brand for which this rule should be applied")
                )

    # ====== CRUD METHODS =======#

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            if values.get("applied_on", False):
                # Ensure item consistency for later searches.
                applied_on = values["applied_on"]
                if applied_on == "3_global":
                    values.update(
                        dict(
                            product_id=None,
                            product_tmpl_id=None,
                            categ_id=None,
                            brand_id=None,
                        )
                    )
                elif applied_on == "2_product_category":
                    values.update(
                        dict(product_id=None, product_tmpl_id=None, brand_id=None)
                    )
                elif applied_on == "1_product":
                    values.update(dict(product_id=None, categ_id=None, brand_id=None))
                elif applied_on == "0_product_variant":
                    values.update(dict(categ_id=None))
                elif applied_on == "brand":
                    values.update(
                        dict(product_id=None, categ_id=None, product_tmpl_id=None)
                    )
        return super().create(vals_list)  # dudas

    def write(self, values):
        if values.get("applied_on", False):
            # Ensure item consistency for later searches.
            applied_on = values["applied_on"]
            if applied_on == "3_global":
                values.update(
                    dict(
                        product_id=None,
                        product_tmpl_id=None,
                        categ_id=None,
                        brand_id=None,
                    )
                )
            elif applied_on == "2_product_category":
                values.update(
                    dict(product_id=None, product_tmpl_id=None, brand_id=None)
                )
            elif applied_on == "1_product":
                values.update(dict(product_id=None, categ_id=None, brand_id=None))
            elif applied_on == "0_product_variant":
                values.update(dict(categ_id=None))
            elif applied_on == "brand":
                values.update(
                    dict(product_id=None, categ_id=None, product_tmpl_id=None)
                )
        return super().write(values)

        # === BUSINESS METHODS ===#

    def _is_applicable_for(self, product, qty_in_product_uom):
        res = super()._is_applicable_for(product, qty_in_product_uom)
        if self.applied_on == "brand":
            if product.brand_id != self.brand_id:
                res = False
        return res
