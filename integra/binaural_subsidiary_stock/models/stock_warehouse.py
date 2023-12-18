from odoo import fields, models


class StockWarehouse(models.Model):
    _inherit = "stock.warehouse"

    subsidiary_id = fields.Many2one(
        "account.analytic.account", string="Subsidiary", domain=[("is_subsidiary", "=", True)]
    )
