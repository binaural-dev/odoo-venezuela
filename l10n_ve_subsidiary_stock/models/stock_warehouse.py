from odoo import fields, models


class StockWarehouse(models.Model):
    _inherit = "stock.warehouse"

    subsidiary_id = fields.Many2one(
        "account.analytic.account",
        string="Subsidiary",
        domain=lambda self: (
            f"[('is_subsidiary', '=', True),('id', 'in', {self.env.user.subsidiary_ids.ids})]"
        ),
    )
    inventory_account_id = fields.Many2one(
        "account.account",
        string="Inventory Account",
        help=(
            "This account will be used to make the valuation move when there is a transfer between"
            " subsidiaries of the same company."
        ),
    )

    company_subsidiary = fields.Boolean(
        related='company_id.subsidiary', string="Company Subsidiary",
    )
