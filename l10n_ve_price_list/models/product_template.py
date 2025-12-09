from odoo import models, fields

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    can_view_list_price_uom = fields.Boolean(
        string='Puede ver unidad de precio',
        compute='_compute_can_view_list_price_uom',
        store=False
    )

    def _compute_can_view_list_price_uom(self):
        for product in self:
            product.can_view_list_price_uom = self.env.user.has_group('l10n_ve_price_list.group_pricelist_see_permission')
