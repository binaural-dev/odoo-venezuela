from odoo import api, fields, models, _
from odoo.tools.sql import column_exists, create_column
import logging
from odoo.exceptions import UserError
_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    bi_igtf = fields.Monetary(string="BI IGTF", help="subtotal with igtf", copy=False, compute='_compute_bi_igtf',store=True)
    amount_paid = fields.Monetary(string="Paid", default=0.00, help="Paid", copy=False)

    igtf_top_aply = fields.Float('Max Igtf amount to be apply', copy=False)
    alter_igtf_top_aply = fields.Float('Max Igtf amount to be apply alter', copy=False)
    alter_bi_igtf = fields.Float('Alter BI IGTF',copy=False)

    foreign_alter_bi_igtf = fields.Float('Foreign Alter BI IGTF',copy=False)
    foreign_bi_igtf = fields.Float(string="foreign BI IGTF", help="foreign subtotal with igtf ", copy=False)

    @api.depends('amount_residual')
    def _compute_bi_igtf(self):
        for rec in self:
            # IGTF base only applies to invoice/refund documents.
            # Payment/accounting entries (move_type=entry) must not go through
            # this computation path, otherwise posting can crash when
            # foreign_inverse_rate is not relevant for that entry.
            if rec.move_type not in ["out_invoice", "out_refund", "in_invoice", "in_refund"]:
                rec.write({
                    'igtf_top_aply': 0.0,
                    'alter_igtf_top_aply': 0.0,
                    'alter_bi_igtf': 0.0,
                    'foreign_alter_bi_igtf': 0.0,
                    'foreign_bi_igtf': 0.0,
                    'bi_igtf': 0.0
                })
                continue

            if rec.journal_id.is_purchase_international:
                
                rec.igtf_top_aply = 0.0
                rec.alter_igtf_top_aply = 0.0
                rec.alter_bi_igtf = 0.0
                rec.foreign_alter_bi_igtf = 0.0
                rec.foreign_bi_igtf = 0.0
                rec.bi_igtf = 0.0
                continue
            
            amount = rec.amount_total 
            if rec.company_currency_id == self.env.ref("base.VEF"):
                amount = rec.foreign_total_billed
            rec.igtf_top_aply = amount * (self.company_id.igtf_percentage / 100)

            if abs(rec.amount_residual) > 0 or rec.payment_state in ['paid', 'in_payment']:
                rec.igtf_top_aply = abs(rec.amount_total_signed) * (self.company_id.igtf_percentage / 100)
                receivable_payable_lines = rec.line_ids.filtered(lambda line: line.account_id.reconcile)

                all_partial_reconciles = receivable_payable_lines.matched_debit_ids | receivable_payable_lines.matched_credit_ids
                final_payment_moves = all_partial_reconciles.mapped('debit_move_id.move_id') | all_partial_reconciles.mapped('credit_move_id.move_id')
                final_payment_moves = final_payment_moves.filtered(lambda m: m.state == 'posted' and m.id != rec.id)

                account = [rec.company_id.customer_account_igtf_id.id, rec.company_id.supplier_account_igtf_id.id]

                total_bi_igtf = 0.0
                igtf_top = 0.0
                alter_bi_igtf = 0.0
                foreign_bi_igtf = 0.0
                foreign_alter_bi_igtf = 0.0

                partner_context = rec.partner_id.with_company(rec.company_id)
                for payment_move in final_payment_moves:
                    if rec.move_type in ['out_invoice', 'out_refund']:
                        target_account = partner_context.property_account_receivable_id
                    else:
                        target_account = partner_context.property_account_payable_id

                    igtf_line = payment_move.line_ids.filtered(lambda line: line.account_id.id in account)
                    partner_line = payment_move.line_ids.filtered(lambda l: l.account_id.id == target_account.id)
                    bank_line = payment_move.line_ids.filtered(
                        lambda line: line.account_id.id not in partner_line.mapped('account_id').ids
                                 and line.account_id.id not in igtf_line.mapped('account_id').ids
                    )

                    igtf_amount = 0.0
                    amount_base_payment = 0.0
                    if bank_line and partner_line:
                        factura_line = rec.line_ids.filtered(lambda l: l.account_id.id == target_account.id)

                        partial = self.env['account.partial.reconcile'].search([
                            '|',
                            '&', ('debit_move_id', 'in', factura_line.ids), ('credit_move_id', 'in', partner_line.ids),
                            '&', ('debit_move_id', 'in', partner_line.ids), ('credit_move_id', 'in', factura_line.ids)
                        ])
                        bank_amount = abs(bank_line[0].amount_currency)
                        bank_amount_balance = abs(bank_line[0].balance)
                        partial_amount = 0.0
                        if partial:
                            partial_amount = abs(sum(partial.mapped('amount')))

                        if igtf_line and partial:
                            igtf_amount = abs(igtf_line[0].balance)
                            igtf_amount_currency = abs(igtf_line[0].amount_currency)
                            partial_amount = abs(sum(partial.mapped('amount')))

                        if not igtf_line and bank_line and partial:
                            igtf_top += partial_amount

                        if igtf_line and bank_line and partial:
                            if (
                                payment_move.payment_id and payment_move.payment_id.reconciled_invoices_count > 1
                            ):
                                amount_base_payment = partial_amount
                            elif (
                                'pos_payment_ids' in bank_line[0].move_id._fields
                                and getattr(bank_line[0].move_id, 'pos_payment_ids', False)
                            ):
                                amount_base_payment = rec.company_id.currency_id.round(
                                    igtf_amount / (rec.company_id.igtf_percentage / 100)
                                )
                            elif rec.company_id.currency_id.round(
                                partial_amount * (rec.company_id.igtf_percentage / 100)
                            ) == igtf_amount:
                                amount_base_payment = partial_amount
                                igtf_amount = amount_base_payment * (rec.company_id.igtf_percentage / 100)
                            else:
                                if rec.company_id.currency_id.round(
                                    bank_amount * (rec.company_id.igtf_percentage / 100)
                                ) == igtf_amount_currency:
                                    amount_base_payment = bank_amount_balance
                                else:
                                    amount_base_payment = partial_amount

                        if igtf_line and partial:
                            alter_bi_igtf += igtf_amount
                            foreign_alter_bi_igtf += igtf_amount_currency

                    conversion_date = rec.invoice_date if rec.invoice_date and payment_move.date <= rec.invoice_date else payment_move.date

                    total_bi_igtf += amount_base_payment
                    if total_bi_igtf > abs(rec.amount_total_signed):
                        total_bi_igtf = abs(rec.amount_total_signed)

                total_bi_igtf += amount_base_payment
                total_foreign_bi_igtf += foreign_amount_base_payment
            apply = rec.igtf_top_aply - (igtf_top * (rec.company_id.igtf_percentage / 100))
            alter_apply = 0.0
            if rec.company_currency_id == self.env.ref("base.VEF"):
                alter_apply = apply / rec.foreign_inverse_rate
            else:
                alter_apply = apply * rec.foreign_inverse_rate
            
            rec.igtf_top_aply = apply
            rec.alter_igtf_top_aply = alter_apply
            rec.alter_bi_igtf = alter_bi_igtf
            rec.foreign_alter_bi_igtf = foreign_alter_bi_igtf
            rec.foreign_bi_igtf = total_foreign_bi_igtf
            rec.bi_igtf = total_bi_igtf
