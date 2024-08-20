from odoo import fields, models


class AccountBankStatementLine(models.Model):
    _inherit = "account.bank.statement.line"

    foreign_amount = fields.Float()

    def _prepare_move_line_default_vals(self, counterpart_account_id=None):
        liquidity_line_vals, counterpart_line_vals = super()._prepare_move_line_default_vals(
            counterpart_account_id=counterpart_account_id
        )
        if not self.env.company.currency_foreign_id.is_zero(self.foreign_amount):
            liquidity_line_vals.update(
                {
                    "foreign_debit": self.foreign_amount > 0 and self.foreign_amount or 0.0,
                    "foreign_credit": self.foreign_amount < 0 and -self.foreign_amount or 0.0,
                    "not_foreign_recalculate": True,
                }
            )
            counterpart_line_vals.update(
                {
                    "foreign_debit": -self.foreign_amount if self.foreign_amount < 0.0 else 0.0,
                    "foreign_credit": self.foreign_amount if self.foreign_amount > 0.0 else 0.0,
                    "not_foreign_recalculate": True,
                }
            )

        return [liquidity_line_vals, counterpart_line_vals]
