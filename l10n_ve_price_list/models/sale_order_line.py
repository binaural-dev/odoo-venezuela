from odoo import models, fields

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    can_edit_prices = fields.Boolean(
        string='Puede editar precios',
        compute='_compute_can_edit_prices',
    )

    def _compute_can_edit_prices(self):
        for line in self:
            line.can_edit_prices = self.env.user.has_group('l10n_ve_price_list.group_pricelist_change_permission')
