from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    update_last_cost = fields.Boolean(default=True, readonly=False)

    variants_are_active = fields.Boolean(compute="_compute_variants_are_active")
    
    latest_standard_price = fields.Monetary(
        compute="_compute_latest_standard_price",
        readonly=False
    )
    
    last_latest_standard_price = fields.Monetary()
    
    @api.depends("product_variant_count")
    def _compute_latest_standard_price(self):
        for product_template in self:
            is_exist_one_variant = product_template.product_variant_count == 1            
            if is_exist_one_variant:
                latest_standard_price = product_template.product_variant_ids.latest_standard_price
                product_template.latest_standard_price = latest_standard_price
                continue
            
            is_more_one_variants = product_template.product_variant_count > 1
            if is_more_one_variants:
                product_template.latest_standard_price = 0.00
                continue

    def _compute_variants_are_active(self):
        for product in self:
            active_variants = self.env["product.product"].get_variants_are_active()
            product.variants_are_active = active_variants