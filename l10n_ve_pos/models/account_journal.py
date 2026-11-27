from odoo import api, models


class AccountJournal(models.Model):
    _inherit = "account.journal"

    @api.constrains("suspense_account_id")
    def _check_pos_methods_distinct_suspense_accounts(self):
        """La cuenta transitoria se cambia en el diario: revisa también aquí los
        métodos de pago que lo usan como diario o como diario afectado de banco
        o efectivo (``pos.payment.method._check_distinct_suspense_accounts``).
        """
        methods = self.env["pos.payment.method"].sudo().with_context(active_test=False).search([
            "|", ("journal_id", "in", self.ids), ("cross_journal", "in", self.ids),
        ])
        methods._check_distinct_suspense_accounts()
