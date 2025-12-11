from odoo import api, fields, models, _
from odoo.tools.sql import column_exists, create_column
from odoo.tools import formatLang
import logging
from odoo.exceptions import UserError
_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    def _auto_init(self):
        if not column_exists(self.env.cr, "account_move", "amount_to_pay_igtf"):
            create_column(self.env.cr, "account_move", "amount_to_pay_igtf", "numeric")
            self.env.cr.execute("""
                UPDATE account_move
                SET amount_to_pay_igtf = 0.0
            """)
        if not column_exists(self.env.cr, "account_move", "amount_residual_igtf"):
            create_column(self.env.cr, "account_move", "amount_residual_igtf", "numeric")
            self.env.cr.execute("""
                UPDATE account_move
                SET amount_residual_igtf = 0.0
            """)
        return super()._auto_init()

    bi_igtf = fields.Monetary(string="BI IGTF", help="subtotal with igtf", copy=False, compute='compute_bi_igtf',store=True)
    amount_paid = fields.Monetary(string="Paid", default=0.00, help="Paid", copy=False)

    payment_igtf_id = fields.Many2one(
        "account.payment",
        string="Payment IGTF",
        help="Payment IGTF",
        readonly=True,
        copy=False,
    )

    amount_to_pay_igtf = fields.Monetary(
        string="IGTF Paid",
        default=0.00,
        help="IGTF Paid",
        compute="_compute_amount_to_pay_igtf",
        store=True,
        copy=False,
    )

    amount_residual_igtf = fields.Monetary(
        string="IGTF Residual",
        default=0.00,
        help="IGTF Residual",
        compute="_compute_amount_residual_igtf",
        copy=False,
    )
    igtf_top_aply = fields.Float('Max Igtf amount to be apply')
    alter_bi_igtf = fields.Float('Alter BI IGTF')
   

    #OVERRIDES ODOO COMPUTE METHOD
    @api.depends('move_type', 'line_ids.amount_residual')
    def _compute_payments_widget_reconciled_info(self):
        for move in self:
            payments_widget_vals = {'title': _('Less Payment'), 'outstanding': False, 'content': []}

            if move.state == 'posted' and move.is_invoice(include_receipts=True):
                reconciled_vals = []
                reconciled_partials = move.sudo()._get_all_reconciled_invoice_partials()
                for reconciled_partial in reconciled_partials:
                    counterpart_line = reconciled_partial['aml']
                    if counterpart_line.move_id.ref:
                        reconciliation_ref = '%s (%s)' % (counterpart_line.move_id.name, counterpart_line.move_id.ref)
                    else:
                        reconciliation_ref = counterpart_line.move_id.name
                    if counterpart_line.amount_currency and counterpart_line.currency_id != counterpart_line.company_id.currency_id:
                        foreign_currency = counterpart_line.currency_id
                    else:
                        foreign_currency = False

                    #-----------------BINAURAL--------------
                    is_igtf = counterpart_line.payment_id.is_igtf_on_foreign_exchange
                    #-----------------BINAURAL--------------

                    reconciled_vals.append({
                        'name': counterpart_line.name,
                        'journal_name': counterpart_line.journal_id.name,
                        'company_name': counterpart_line.journal_id.company_id.name if counterpart_line.journal_id.company_id != move.company_id else False,
                        #-----------------BINAURAL--------------
                        'amount': reconciled_partial['amount'] + move.amount_to_pay_igtf if is_igtf else reconciled_partial['amount'], 
                        #-----------------BINAURAL--------------
                        'currency_id': move.company_id.currency_id.id if reconciled_partial['is_exchange'] else reconciled_partial['currency'].id,
                        'date': counterpart_line.date,
                        'partial_id': reconciled_partial['partial_id'],
                        'account_payment_id': counterpart_line.payment_id.id,
                        'payment_method_name': counterpart_line.payment_id.payment_method_line_id.name,
                        'move_id': counterpart_line.move_id.id,
                        'ref': reconciliation_ref,
                        # these are necessary for the views to change depending on the values
                        'is_exchange': reconciled_partial['is_exchange'],
                        'amount_company_currency': formatLang(self.env, abs(counterpart_line.balance), currency_obj=counterpart_line.company_id.currency_id),
                        'amount_foreign_currency': foreign_currency and formatLang(self.env, abs(counterpart_line.amount_currency), currency_obj=foreign_currency)
                    })
                payments_widget_vals['content'] = reconciled_vals

            if payments_widget_vals['content']:
                move.invoice_payments_widget = payments_widget_vals
            else:
                move.invoice_payments_widget = False


    @api.depends("tax_totals")
    def _compute_amount_to_pay_igtf(self):
        """
        Compute the amount to pay of the IGTF
        """
        for move in self:
            move.amount_to_pay_igtf = 0
            if move.invoice_line_ids and move.is_invoice(include_receipts=True) and move.tax_totals:
                move.amount_to_pay_igtf = move.tax_totals["igtf"]["igtf_amount"] - move.amount_paid

    @api.depends(
        "amount_total", "amount_residual", "amount_residual_igtf", "amount_to_pay_igtf", "bi_igtf"
    )
    def _compute_amount_residual_igtf(self):
        for record in self:
            record.amount_residual_igtf = record.amount_residual + record.amount_to_pay_igtf

            if record.amount_residual and record.amount_to_pay_igtf:
                record.amount_residual_igtf = record.amount_residual + record.amount_to_pay_igtf
            else:
                record.amount_residual_igtf = 0

    @api.depends(
        "bi_igtf",
    )
    def _compute_tax_totals(self):
        return super()._compute_tax_totals()

    @api.depends('amount_residual')
    def compute_bi_igtf(self):
        for rec in self:

            rec.igtf_top_aply = rec.currency_id.round((rec.amount_total * (self.company_id.igtf_percentage / 100)))

            receivable_payable_lines = rec.line_ids.filtered(lambda line: line.account_id.reconcile)

            account = [self.company_id.customer_account_igtf_id.id,self.company_id.supplier_account_igtf_id.id ]
            payment_moves = self.env['account.move']
            
            all_partial_reconciles = receivable_payable_lines.matched_debit_ids | receivable_payable_lines.matched_credit_ids
            
            payment_moves |= all_partial_reconciles.mapped('debit_move_id.move_id')
            payment_moves |= all_partial_reconciles.mapped('credit_move_id.move_id')

            final_payment_moves = payment_moves.filtered(lambda m: m.state == 'posted' and m.id != rec.id)
            total_bi_igtf = 0.0
            igtf_top = 0.0
            alter_bi_igtf = 0.0
            for payment_move in final_payment_moves:
                
                igtf_line = payment_move.line_ids.filtered(lambda line: line.account_id.id in account)
                bank_line = payment_move.line_ids.filtered(lambda line: line.account_id.account_type in ['asset_cash','bank'])

                if not igtf_line and bank_line: #bolivares
                    
                    igtf_top += abs(bank_line[0].balance)

                base_pago = 0.0

                if igtf_line and bank_line:
                  
                    base_pago = abs(bank_line[0].foreign_balance) if bank_line[0].currency_id == self.env.ref("base.VEF") else abs(bank_line[0].balance)
                    
                if igtf_line:
                    
                    alter_bi_igtf += abs(bank_line[0].foreign_balance) if bank_line[0].currency_id == self.env.ref("base.VEF") else abs(igtf_line[0].balance)
                total_bi_igtf += base_pago
            
            apply = rec.igtf_top_aply - (igtf_top * (rec.company_id.igtf_percentage / 100))
            rec.write({
                'igtf_top_aply': apply,
                'alter_bi_igtf': alter_bi_igtf
            })
            rec.bi_igtf = total_bi_igtf
                    


