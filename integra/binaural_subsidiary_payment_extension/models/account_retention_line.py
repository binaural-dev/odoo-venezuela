from odoo import fields, models


class AccountRetentionLine(models.Model):
    _inherit = "account.retention.line"

    account_analytic_id = fields.Many2one(
        "account.analytic.account",
        string="Subsidiary",
        related="move_id.account_analytic_id",
        store=True,
    )
