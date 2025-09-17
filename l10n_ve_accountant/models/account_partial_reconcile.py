from odoo import fields, models


class AccountPartialReconcile(models.Model):
    _inherit = "account.partial.reconcile"

    debit_move_foreign_inverse_rate = fields.Float(
        related="debit_move_id.foreign_inverse_rate",
        store=True,
        index=True,
    )
    credit_move_foreign_inverse_rate = fields.Float(
        related="credit_move_id.foreign_inverse_rate",
        store=True,
        index=True,
    )
    foreign_credit = fields.Monetary(
        string="Foreign Credit",
        related="credit_move_id.foreign_balance",
        currency_field="credit_foreign_currency_id",
        store=True,
    )
    foreign_debit = fields.Monetary(
        string="Foreign Debit",
        related="debit_move_id.foreign_balance",
        currency_field="debit_foreign_currency_id",
        store=True,
    )
    credit_foreign_currency_id = fields.Many2one(
        related="credit_move_id.foreign_currency_id",
        store=True,
        index=True,
    )
    debit_foreign_currency_id = fields.Many2one(
        related="debit_move_id.foreign_currency_id",
        store=True,
        index=True,
    )
