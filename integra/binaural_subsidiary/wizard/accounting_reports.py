from odoo import fields, models


class AccountingReports(models.TransientModel):
    _inherit = "wizard.accounting.reports"

    account_analytic_id = fields.Many2one(
        "account.analytic.account",
        domain=lambda self: (
            f"[('is_subsidiary', '=', True),('id', 'in', {self.env.user.subsidiary_ids.ids})]"
        ),
        string="Subsidiary",
    )

    def search_moves(self):
        moves = super().search_moves()
        if not self.account_analytic_id:
            return moves
        return moves.filtered_domain([("account_analytic_id", "=", self.account_analytic_id.id)])
