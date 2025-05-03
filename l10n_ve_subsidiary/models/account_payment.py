from odoo import fields, models, _, api
from odoo.osv import expression
from odoo.exceptions import ValidationError, UserError

import logging

_logger = logging.getLogger(__name__)

class AccountPayment(models.Model):
    _inherit = "account.payment"

    account_analytic_id = fields.Many2one(
        "account.analytic.account",
        string="Subsidiary",
        domain=lambda self: (
            f"[('is_subsidiary', '=', True),('id', 'in', {self.env.user.subsidiary_ids.ids})]"
        ),
        default=lambda self: self.env.user.subsidiary_id.id,
        tracking=True,
    )

    company_subsidiary = fields.Boolean(
        related="company_id.subsidiary",
        string="Company Subsidiary",
    )

    @api.depends('payment_type', 'account_analytic_id')
    def _compute_available_journal_ids(self):
        """
        Get all journals having at least one payment method for inbound/outbound depending on the payment_type.
        """
        domain = [
            ('company_id', 'in', self.company_id.ids),
            ('type', 'in', ('bank', 'cash'))
        ]

        get_domain_subsidiaries_suitable_journals = self.env["account.journal"].get_domain_subsidiaries_suitable_journals

        for pay in self:
            domain = get_domain_subsidiaries_suitable_journals(domain, pay.account_analytic_id.id)
            journals = self.env['account.journal'].search(domain)

            if pay.payment_type == 'inbound':
                pay.available_journal_ids = journals.filtered(
                    lambda j: j.company_id == pay.company_id and j.inbound_payment_method_line_ids.ids != []
                )
            else:
                pay.available_journal_ids = journals.filtered(
                    lambda j: j.company_id == pay.company_id and j.outbound_payment_method_line_ids.ids != []
                )

    def _synchronize_to_moves(self, changed_fields):
        """
        Override the original method to change the analytic account (subidiary) of the move using
        the one from the payment.
        """
        res = super()._synchronize_to_moves(changed_fields)
        for payment in self.with_context(skip_account_move_synchronization=True):
            if not payment.account_analytic_id:
                continue
            payment.move_id.write({"account_analytic_id": payment.account_analytic_id.id})
        return res

    def _synchronize_from_moves(self, changed_fields):
        """
        Override the original method to change the analytic account (subidiary) of the payment using
        the one from the move.
        """
        res = super()._synchronize_from_moves(changed_fields)
        for payment in self.with_context(skip_account_move_synchronization=True):
            move = payment.move_id
            if move.statement_line_id:
                continue

            if not move.account_analytic_id:
                continue
            payment.write({"account_analytic_id": move.account_analytic_id.id})
        return res

    def correccion_subsidiary_account_payment(self):
        for payment in self:
            move = payment.move_id
            if move.invoice_line_ids:
                subsidiary_id = move.invoice_line_ids[0].analytic_distribution
                if subsidiary_id:
                    subsidiary_id = subsidiary_id.keys()
                    for subsidiary in subsidiary_id:
                        subsidiary_id = subsidiary
                    payment.account_analytic_id = self.env["account.analytic.account"].search(
                        [("id", "=", subsidiary_id)]
                    )

    @api.onchange('journal_id', 'account_analytic_id')
    def _onchange_subsidiary_related_fields(self):
        for record in self:
            if not record.journal_id:
                continue
            record.journal_id.check_journal_selected(record.account_analytic_id.id)