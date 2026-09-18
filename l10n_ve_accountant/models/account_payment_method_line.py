from odoo import api, fields, models


class AccountPaymentMethodLine(models.Model):
    _inherit = "account.payment.method.line"

    payment_account_id = fields.Many2one(default=lambda self: self._default_payment_account_id())

    def _default_payment_account_id(self):
        journal_id = self.env.context.get('default_journal_id')
        if not journal_id:
            return False
        journal = self.env['account.journal'].browse(journal_id)
        if journal.type == 'bank':
            return journal.default_account_id.id
        return False
