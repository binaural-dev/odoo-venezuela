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

    foreign_currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_foreign_id",
        store=True,
    )
    debit_foreign_currency_id = fields.Many2one(
        "res.currency",
        related="debit_move_id.foreign_currency_id",
        store=True,
        precompute=True,
    )
    credit_foreign_currency_id = fields.Many2one(
        "res.currency",
        related="credit_move_id.foreign_currency_id",
        store=True,
        precompute=True,
    )
    foreign_amount = fields.Monetary(
        currency_field="foreign_currency_id",
        help="Always positive amount concerned by this matching expressed in the company's foreign currency.",
    )
    debit_foreign_amount_currency = fields.Monetary(
        currency_field="debit_foreign_currency_id",
        help="Always positive amount concerned by this matching expressed in the debit line foreign currency.",
    )
    credit_foreign_amount_currency = fields.Monetary(
        currency_field="credit_foreign_currency_id",
        help="Always positive amount concerned by this matching expressed in the credit line foreign currency.",
    )