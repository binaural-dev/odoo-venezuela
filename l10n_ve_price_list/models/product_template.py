from odoo import models, fields

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    hide_list_price = fields.Boolean(
        compute='_compute_hide_list_price',
        store=False
    )

    def _compute_hide_list_price(self):
        for product in self:
            product.hide_list_price = self.env.user.has_group('l10n_ve_price_list.group_hide_product_sale_prices')
