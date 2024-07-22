from odoo import api, fields, models

class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    liters_per_unit_total = fields.Float(
        compute="_compute_liters_per_unit_total", store=True, digits='Stock Weight'
    )

    @api.depends("quantity", "product_id")
    def _compute_liters_per_unit_total(self):
        for line in self:
            line.liters_per_unit_total = 0
            line.liters_per_unit_total = line.quantity * line.product_id.liters_per_unit