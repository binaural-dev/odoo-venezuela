from odoo import fields, models


class StockWarehouse(models.Model):
    _inherit = "stock.warehouse"

    subsidiary_id = fields.Many2one(
        "account.analytic.account", string="Subsidiary", domain=[("is_subsidiary", "=", True)]
    )
    inventory_account_id = fields.Many2one(
        "account.account",
        string="Inventory Account",
        help=(
            "This account will be used to make the valuation move when there is a transfer between"
            " subsidiaries of the same company."
        ),
    )
