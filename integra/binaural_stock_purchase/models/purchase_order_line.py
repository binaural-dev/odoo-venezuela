from odoo import api, fields, models, _


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    liters_per_unit_total = fields.Float(
        compute="_compute_liters_per_unit_total", store=True, digits='Stock Weight'
    )
    
    @api.depends("product_qty", "product_uom")
    def _compute_liters_per_unit_total(self):
        for line in self:
            line.liters_per_unit_total = 0
            line.liters_per_unit_total = line.product_qty * (line.product_uom.factor_inv * line.product_id.liters_per_unit)