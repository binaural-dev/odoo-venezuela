from odoo import models, fields

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    can_edit_prices = fields.Boolean(compute="_compute_can_edit_prices")
    
    def _compute_can_edit_prices(self):
        for line in self:
            line.can_edit_prices = self.env.user.has_group("l10n_ve_price_list.group_pricelist_change_permission_sale")

    can_edit_vendor_invoice_prices = fields.Boolean(
        string="Puede editar precios en facturas de proveedor",
        compute="_compute_can_edit_pricelist_vendor",
    )  
    
    def _compute_can_edit_pricelist_vendor(self):
        for move in self:
            move.can_edit_vendor_invoice_prices = self.env.user.has_group("binaural_purchase.group_foreign_price_edit_purchase")
