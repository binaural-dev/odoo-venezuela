from odoo import api, fields, models, _
from odoo.tools.sql import column_exists, create_column
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
    foreign_bi_igtf = fields.Monetary(string="Foreign Bi Igtf", help="foreign subtotal with igtf", copy=False, compute='compute_foreign_bi_igtf',store=True)
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
    igtf_top_aply = fields.Float('Max Igtf amount to be apply', copy=False)
    alter_igtf_top_aply = fields.Float('Max Igtf amount to be apply alter', copy=False)
    alter_bi_igtf = fields.Float('Alter BI IGTF',copy=False)
    foreign_alter_bi_igtf = fields.Float('Foreign Alter BI IGTF',copy=False)

    foreign_alter_bi_igtf = fields.Float('Foreign Alter BI IGTF',copy=False)
    foreign_bi_igtf = fields.Float(string="foreign BI IGTF", help="foreign subtotal with igtf ", copy=False)


    @api.depends("tax_totals")
    def _compute_amount_to_pay_igtf(self):
        """
        Compute the amount to pay of the IGTF
        """
        for move in self:
            move.amount_to_pay_igtf = 0
            if move.invoice_line_ids and move.is_invoice(include_receipts=True) and move.tax_totals:
                if move.company_currency_id != self.env.ref("base.VEF"):

                    move.amount_to_pay_igtf = move.tax_totals["igtf"]["igtf_amount"] - move.amount_paid

                else:
                    move.amount_to_pay_igtf = move.tax_totals["igtf"]["foreign_igtf_amount"] - move.amount_paid
            if move.journal_id.is_purchase_international:
                move.amount_to_pay_igtf = 0.0

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
            if rec.journal_id.is_purchase_international:
                rec.write({
                    'igtf_top_aply': 0.0,
                    'alter_igtf_top_aply': 0.0,
                    'alter_bi_igtf': 0.0,
                    'foreign_alter_bi_igtf': 0.0,
                    'foreign_bi_igtf': 0.0,
                    'bi_igtf': 0.0
                })
                continue
            
            amount = rec.amount_total
            if rec.company_currency_id == self.env.ref("base.VEF"):
                amount = rec.foreign_total_billed
            rec.igtf_top_aply = amount * (self.company_id.igtf_percentage / 100)

            if rec.company_currency_id == self.env.ref("base.VEF"):
                rec.alter_igtf_top_aply = rec.igtf_top_aply / rec.foreign_inverse_rate
            else:
                rec.alter_igtf_top_aply = rec.igtf_top_aply * rec.foreign_inverse_rate

            receivable_payable_lines = rec.line_ids.filtered(lambda line: line.account_id.reconcile)

            account = [self.company_id.customer_account_igtf_id.id,self.company_id.supplier_account_igtf_id.id ]
            
            payment_moves = self.env['account.move']
           
            all_partial_reconciles = receivable_payable_lines.matched_debit_ids | receivable_payable_lines.matched_credit_ids
            
            payment_moves |= all_partial_reconciles.mapped('debit_move_id.move_id')
            payment_moves |= all_partial_reconciles.mapped('credit_move_id.move_id')

            final_payment_moves = payment_moves.filtered(lambda m: m.state == 'posted' and m.id != rec.id)
            total_bi_igtf = 0.0
            total_foreign_bi_igtf = 0.0
            igtf_top = 0.0
            alter_bi_igtf = 0.0
            foreign_alter_bi_igtf = 0.0
            bank_amount = 0.0

            foreign_bank_amount = 0.0
            foreign_igtf_amount = 0.0
            target_account = False

            partial_amount = 0.0
            partial_foreign_amount = 0.0
            partner_context = rec.partner_id.with_company(rec.company_id)
            for payment_move in final_payment_moves:
                igtf_line = payment_move.line_ids.filtered(lambda line: line.account_id.id in account)
                bank_line = payment_move.line_ids.filtered(lambda line: line.account_id.account_type in ['asset_cash','asset_receivable'])
                
                if rec.move_type in ['out_invoice', 'out_refund']:
                    target_account = partner_context.property_account_receivable_id
                else:
                    target_account = partner_context.property_account_payable_id

                factura_line = rec.line_ids.filtered(lambda l: l.account_id.id == target_account.id)

                pago_line = payment_move.line_ids.filtered(lambda l: l.account_id.id == target_account.id)
                
                partial = self.env['account.partial.reconcile'].search([
                    '|',
                    '&', ('debit_move_id', '=', factura_line.id), ('credit_move_id', 'in', pago_line.ids),
                    '&', ('debit_move_id', 'in', pago_line.ids), ('credit_move_id', '=', factura_line.id)
                ], limit=1)

                if partial:
                    if bank_line and bank_line[0].company_currency_id == self.env.ref("base.VEF"):
                        partial_amount = abs(partial.foreign_amount)
                        partial_foreign_amount = abs(partial.amount)
                    else:
                        partial_amount = abs(partial.amount)
                        partial_foreign_amount = abs(partial.foreign_amount)

                if bank_line:
                   
                    bank_amount = partial_amount
                    foreign_bank_amount = partial_foreign_amount
                        
               
                if igtf_line:
                    if igtf_line[0].company_currency_id == self.env.ref("base.VEF"):
                        igtf_amount = abs(igtf_line[0].foreign_balance) 
                        foreign_igtf_amount = abs(igtf_line[0].balance) 
                    else:
                        igtf_amount = abs(igtf_line[0].balance)
                        foreign_igtf_amount = abs(igtf_line[0].foreign_balance) 


                if not igtf_line and bank_line:
                    
                    igtf_top += bank_amount



                amount_base_payment = 0.0
                foreign_amount_base_payment = 0.0

                if igtf_line and bank_line:

                    if payment_move.payment_id and payment_move.payment_id.reconciled_invoices_count > 1:

                        amount_base_payment = partial_amount
                        foreign_amount_base_payment = partial_foreign_amount
                    

                    elif (bank_amount* (rec.company_id.igtf_percentage / 100)) < igtf_amount:
                        if (bank_amount * (rec.company_id.igtf_percentage / 100)) == igtf_amount:
                            
                            amount_base_payment = bank_amount
                            foreign_amount_base_payment = foreign_bank_amount
                        else:
                            
                            amount_base_payment = igtf_amount / (rec.company_id.igtf_percentage / 100)
                            foreign_amount_base_payment = foreign_igtf_amount / (rec.company_id.igtf_percentage / 100)

                        
                        if 'pos_payment_ids' in bank_line[0].move_id._fields:
                            if bank_line[0].move_id.pos_payment_ids:
                                amount_base_payment = igtf_amount / (rec.company_id.igtf_percentage / 100)
                                foreign_amount_base_payment = foreign_igtf_amount / (rec.company_id.igtf_percentage / 100)
                    else:
                        

                        amount_base_payment = igtf_amount / (rec.company_id.igtf_percentage / 100)
                        foreign_amount_base_payment = foreign_igtf_amount / (rec.company_id.igtf_percentage / 100)

                if igtf_line:
                    
                    alter_bi_igtf += igtf_amount
                    foreign_alter_bi_igtf += foreign_igtf_amount

                total_bi_igtf += amount_base_payment
                total_foreign_bi_igtf += foreign_amount_base_payment
            
            
            apply = rec.igtf_top_aply - (igtf_top * (rec.company_id.igtf_percentage / 100))
            alter_apply = 0.0
            if rec.company_currency_id == self.env.ref("base.VEF"):
                alter_apply = apply / rec.foreign_inverse_rate
            else:
                alter_apply = apply * rec.foreign_inverse_rate

            
            rec.write({
                'igtf_top_aply': apply,
                'alter_igtf_top_aply': alter_apply,
                'alter_bi_igtf': alter_bi_igtf,
                'foreign_alter_bi_igtf': foreign_alter_bi_igtf,
                'foreign_bi_igtf': total_foreign_bi_igtf
            })
            rec.bi_igtf = total_bi_igtf
                    
    @api.depends('bi_igtf')
    def compute_foreign_bi_igtf(self):
        """
        Compute the foreign currency taxable base (BI) for IGTF and the foreign IGTF amount.

        The calculation is based on the
        reconciled payment moves linked to the invoice and the company's IGTF
        configuration.

        Main logic:
            1. Uses the invoice foreign total billed amount as the base reference.
            2. Computes the theoretical IGTF amount using the company's IGTF percentage.
            3. Retrieves all posted payment moves reconciled with the invoice.
            4. For each payment:
                - Identifies the bank/cash line.
                - Identifies the receivable/payable (CxC/CxP) line.
                - Identifies the IGTF tax line.
            5. Determines the taxable base for each payment depending on whether
            the IGTF line matches the expected percentage.
            6. Accumulates:
                - The total taxable base in foreign currency.
                - The total IGTF amount actually charged.
            7. Computes the adjusted IGTF amount by excluding payments without IGTF.
        """
        for rec in self:            
            amount = rec.foreign_total_billed

            igtf_top_aply = rec.currency_id.round((amount * (self.company_id.igtf_percentage / 100)))

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
            bank_amount = 0.0
            cxc_amount = 0.0
            
            for payment_move in final_payment_moves:
                igtf_line = payment_move.line_ids.filtered(lambda line: line.account_id.id in account)
                bank_line = payment_move.line_ids.filtered(lambda line: line.account_id.account_type in ['asset_cash','asset_current','liability_current'])
                cxc = [payment_move.partner_id.property_account_receivable_id.id, payment_move.partner_id.property_account_payable_id.id]
                cxc_line = payment_move.line_ids.filtered(lambda line: line.account_id.id in cxc)

                if bank_line:
                    bank_amount = abs(bank_line[0].foreign_balance) 

                if cxc_line:
                    cxc_amount = abs(cxc_line[0].foreign_balance) 

                if igtf_line:
                    igtf_amount = abs(igtf_line[0].foreign_balance)
  
                if not igtf_line and bank_line:
                   
                    igtf_top += bank_amount

                amount_base_payment = 0.0

                if igtf_line and bank_line:
                   
                    if (bank_amount* (rec.company_id.igtf_percentage / 100)) > igtf_amount:
                       
                        amount_base_payment = cxc_amount
                    else:
                        
                        amount_base_payment = bank_amount

                if igtf_line:
                    
                    alter_bi_igtf += igtf_amount

                total_bi_igtf += amount_base_payment
            
            apply = igtf_top_aply - (igtf_top * (rec.company_id.igtf_percentage / 100))
            rec.foreign_alter_bi_igtf = alter_bi_igtf
            rec.foreign_bi_igtf = total_bi_igtf
