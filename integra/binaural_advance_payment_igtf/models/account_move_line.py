from odoo import api, fields, models, _, Command
from odoo.exceptions import UserError
from datetime import date, timedelta

import logging

_logger = logging.getLogger(__name__)



class AccountMoveLine(models.Model):
    _inherit = "account.move.line"
    

    # def reconcile(self):
    #     ''' Reconcile the current move lines all together.
    #     :return: A dictionary representing a summary of what has been done during the reconciliation:
    #             * partials:             A recorset of all account.partial.reconcile created during the reconciliation.
    #             * exchange_partials:    A recorset of all account.partial.reconcile created during the reconciliation
    #                                     with the exchange difference journal entries.
    #             * full_reconcile:       An account.full.reconcile record created when there is nothing left to reconcile
    #                                     in the involved lines.
    #             * tax_cash_basis_moves: An account.move recordset representing the tax cash basis journal entries.
    #     '''
    #     results = {'exchange_partials': self.env['account.partial.reconcile']}

    #     if not self:
    #         return results

    #     not_paid_invoices = self.move_id.filtered(lambda move:
    #         move.is_invoice(include_receipts=True)
    #         and move.payment_state not in ('paid', 'in_payment')
    #     )

    #     # ==== Check the lines can be reconciled together ====
    #     company = None
    #     account = None
    #     for line in self:
    #         if line.reconciled:
    #             _logger.warning("LINEEEEE RECONCILIADA %s", line.name)
    #             raise UserError(_("You are trying to reconcile some entries that are already reconciled."))
    #         if not line.account_id.reconcile and line.account_id.account_type not in ('asset_cash', 'liability_credit_card'):
    #             raise UserError(_("Account %s does not allow reconciliation. First change the configuration of this account to allow it.")
    #                             % line.account_id.display_name)
    #         if line.move_id.state != 'posted':
    #             raise UserError(_('You can only reconcile posted entries.'))
    #         if company is None:
    #             company = line.company_id
    #         elif line.company_id != company:
    #             raise UserError(_("Entries doesn't belong to the same company: %s != %s")
    #                             % (company.display_name, line.company_id.display_name))
    #         if account is None:
    #             account = line.account_id
    #         elif line.account_id != account:
    #             raise UserError(_("Entries are not from the same account: %s != %s")
    #                             % (account.display_name, line.account_id.display_name))

    #     sorted_lines = self.sorted(key=lambda line: (line.date_maturity or line.date, line.currency_id, line.amount_currency))

    #     # ==== Collect all involved lines through the existing reconciliation ====

    #     involved_lines = sorted_lines._all_reconciled_lines()
    #     involved_partials = involved_lines.matched_credit_ids | involved_lines.matched_debit_ids

    #     # ==== Create partials ====

    #     partial_no_exch_diff = bool(self.env['ir.config_parameter'].sudo().get_param('account.disable_partial_exchange_diff'))
    #     sorted_lines_ctx = sorted_lines.with_context(no_exchange_difference=self._context.get('no_exchange_difference') or partial_no_exch_diff)
    #     partials = sorted_lines_ctx._create_reconciliation_partials()
    #     results['partials'] = partials
    #     involved_partials += partials
    #     exchange_move_lines = partials.exchange_move_id.line_ids.filtered(lambda line: line.account_id == account)
    #     involved_lines += exchange_move_lines
    #     exchange_diff_partials = exchange_move_lines.matched_debit_ids + exchange_move_lines.matched_credit_ids
    #     involved_partials += exchange_diff_partials
    #     results['exchange_partials'] += exchange_diff_partials

    #     # ==== Create entries for cash basis taxes ====

    #     is_cash_basis_needed = account.company_id.tax_exigibility and account.account_type in ('asset_receivable', 'liability_payable')
    #     if is_cash_basis_needed and not self._context.get('move_reverse_cancel'):
    #         tax_cash_basis_moves = partials._create_tax_cash_basis_moves()
    #         results['tax_cash_basis_moves'] = tax_cash_basis_moves