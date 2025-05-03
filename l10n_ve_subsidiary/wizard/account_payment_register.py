from odoo import api, fields, models, _
import logging

_logger = logging.getLogger(__name__)

class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"

    account_analytic_id = fields.Many2one(
        "account.analytic.account",
        string="Subsidiary",
        domain=lambda self: (
            f"[('is_subsidiary', '=', True),('id', 'in', {self.env.user.subsidiary_ids.ids})]"
        ),
        readonly=True
    )

    company_subsidiary = fields.Boolean(
        related='company_id.subsidiary'
    )

    def _init_payments(self, to_process, edit_mode=False):
        """
        Override the original method to add the analytic account to the payments.
        """
        payments = super()._init_payments(to_process, edit_mode)
        for payment in payments:
            payment.account_analytic_id = self.account_analytic_id.id
        return payments

    @api.depends('payment_type', 'company_id', 'can_edit_wizard', 'account_analytic_id')
    def _compute_available_journal_ids(self):
        for wizard in self:
            available_journal_ids = self.env['account.journal']

            if wizard.can_edit_wizard:
                batch = wizard._get_batches()[0]
                available_journal_ids = wizard._get_batch_available_journals(batch)
            else:
                available_journal_ids = self.env['account.journal'].search([
                    ('company_id', '=', wizard.company_id.id),
                    ('type', 'in', ('bank', 'cash')),
                ])

            wizard.available_journal_ids = available_journal_ids.filtered( lambda w: w.subsidiary_id.id in [False, wizard.account_analytic_id.id])
