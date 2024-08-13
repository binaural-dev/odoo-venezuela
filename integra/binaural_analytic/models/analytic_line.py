from odoo import fields, models


class AccountAnalyticLine(models.Model):
    _inherit = "account.analytic.line"

    foreign_amount = fields.Monetary(
        currency_field="foreign_currency_id",
        default=0.0,
    )

    foreign_currency_id = fields.Many2one(
        related="company_id.currency_foreign_id",
        string="Foreign Currency",
    )
