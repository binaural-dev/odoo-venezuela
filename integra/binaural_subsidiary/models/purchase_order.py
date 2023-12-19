from odoo import fields, models, _


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    account_analytic_id = fields.Many2one(
        "account.analytic.account",
        string="Subsidiary",
        domain=[("is_subsidiary", "=", True)],
    )
