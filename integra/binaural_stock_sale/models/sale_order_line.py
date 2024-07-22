from odoo import api, fields, models, _


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    liters_per_unit_total = fields.Float(
        compute="_compute_liters_per_unit_total", store=True, digits='Stock Weight'
    )

    @api.depends("product_uom", "product_uom_qty")
    def _compute_liters_per_unit_total(self):
        for line in self:
            line.liters_per_unit_total = 0
            line.liters_per_unit_total = line.product_uom_qty * (line.product_uom.factor_inv * line.product_id.liters_per_unit)