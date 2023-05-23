from odoo import api, fields, models


class ProductProduct(models.Model):
    _inherit = "product.product"

    latest_standard_price = fields.Monetary(
        compute="_compute_latest_standard_price",
        store=True,
        readonly=False
    )
    
    last_latest_standard_price = fields.Monetary()

    @api.depends("product_tmpl_id.latest_standard_price")
    def _compute_latest_standard_price(self):
        """
        Ensures that when the user changes the latest standard price of the product template and
        product variants are not active, the variants's latest standard price is updated.

        This is made because when variants are not active the user only has acces to the product
        template and not to the product variants (product.product model), but the variants still
        exist and should updated when the latest standard price of the product template is changed.

        However, if variants are active the user should change the latest standard price of each
        one of the variants and not of the product template directly.
        """
        variants_are_active = self.get_variants_are_active()

        if variants_are_active:
            return

        for product in self:
            latest_standard_price = product.product_tmpl_id.latest_standard_price
            product.latest_standard_price = latest_standard_price

    @api.model
    def get_variants_are_active(self):
        current_user = self.env["res.users"].browse(self._uid)
        return current_user.has_group("product.group_product_variant")
