from odoo import fields, models


class AccountBankStatementLine(models.Model):
    _inherit = "account.bank.statement.line"

    pos_cross_real_move_id = fields.Many2one(
        "account.move",
        string="PoS Cross Move (Real Journal)",
        readonly=True,
        copy=False,
        index="btree_not_null",
        help="PoS cross move that created this statement line in its real journal.",
    )
