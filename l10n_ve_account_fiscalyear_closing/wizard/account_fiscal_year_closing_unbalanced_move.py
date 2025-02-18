from odoo import fields, models


class AccountFiscalYearClosingUnbalancedMove(models.TransientModel):
    _inherit = "account.fiscalyear.closing.unbalanced.move"

    foreign_currency_rate = fields.Float(string="Rate")


class AccountFiscalYearClosingUnbalancedMoveLine(models.TransientModel):
    _inherit = "account.fiscalyear.closing.unbalanced.move.line"

    foreign_credit = fields.Float()
    foreign_debit = fields.Float()
