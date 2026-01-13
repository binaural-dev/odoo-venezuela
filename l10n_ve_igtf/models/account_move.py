from odoo import api, fields, models, _
from odoo.tools.sql import column_exists, create_column
from odoo.tools import formatLang
import logging

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
    alter_bi_igtf = fields.Float('Alter BI IGTF',copy=False)
    foreign_alter_bi_igtf = fields.Float('Foreign Alter BI IGTF',copy=False)


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

    def recalculate_bi_igtf(self, line_id=None, initial_residual=0.0,amount_to_pay = 0.0):
        """This method can be used by ir.actions.server to update bi_igtf"""
        _logger.info(f'self.bi_igtf === {self.move_type}')
        _logger.info(f' jajajaja line_id === {line_id}')
        _logger.warning(f'Initial residual: {initial_residual}')
        for record in self:
            bi_igtf = 0
            credits_for_payment = {}
            move_id = record.id
            # _logger.info(f'record.invoice_payments_widget === {record.invoice_payments_widget}')
            if not record.invoice_payments_widget:
                record.bi_igtf = 0
                _logger.info('No tiene pagos relacionados')
                continue
                
            if record.bi_igtf > 0 and any(
            payment.get("account_payment_id", False) for payment in record.invoice_payments_widget.get("content", [])
            if payment.get("account_payment_id", False)
            ):
                _logger.info('Tiene pagos relacionados')
                advance_igtf = False
                for payment in record.invoice_payments_widget.get("content", []):
                    move_id = payment.get('move_id')
                    _logger.info(f'move_id === {move_id}')
                    payment_id = self.env['account.move'].browse(move_id)
                    if not payment_id:
                        continue
                    is_igtf = payment_id.line_ids.filtered(
                        lambda l: l.account_id == self.env.company.customer_account_igtf_id or l.account_id == self.env.company.supplier_account_igtf_id
                    )
                    if is_igtf:
                        advance_igtf = True  # SI CONSIGUE LINEA IGTF EN EL PAGO
                        credits_for_payment[move_id] = payment_id.amount_total
                _logger.warning('iterando')
                bi_igtf = sum(credits_for_payment.values())
                if bi_igtf > record.amount_total and not initial_residual == 0:
                    bi_igtf = initial_residual + record.bi_igtf
                    record.bi_igtf = bi_igtf
                    return
                if not advance_igtf:
                    record.bi_igtf = 0.00
                elif bi_igtf:
                    record.bi_igtf = bi_igtf
                return
            if line_id:
                _logger.info(f'tiene line_id === {line_id}')
                line = self.env["account.move.line"].browse([line_id])
                _logger.info(f'line.move_id === {line.read([])}')
                payment_id = line.move_id.payment_id
                if payment_id and payment_id.is_igtf_on_foreign_exchange:
                    _logger.info(f'tiene payment_id igtf === {payment_id.id}')
                    # payment_id = line.move_id.payment_id
                    bi_igtf = payment_id.get_bi_igtf(move_id)
                    _logger.info(f'tiene payment_id igtf === {bi_igtf}')
                    if initial_residual <= bi_igtf and bi_igtf >= amount_to_pay:
                        record.bi_igtf = min(record.bi_igtf + bi_igtf,amount_to_pay)
                        _logger.warning(f'Hey 22222222222 {record.bi_igtf}')
                        bi_igtf = 0
                        continue
                    elif initial_residual <= bi_igtf:
                        record.bi_igtf = initial_residual
                        _logger.warning(f'Hey {record.bi_igtf}')
                        continue
                    record.bi_igtf = min(record.bi_igtf + bi_igtf,record.amount_total)
                    _logger.warning(f'Hey 33333333333 {record.bi_igtf}')
                    continue
                else:
                    payment_id = line.move_id.payment_id
                    bi_igtf = initial_residual if initial_residual else record.amount_total
                    _logger.info(f'asignando el bi igtf === {bi_igtf}')
                    if initial_residual <= bi_igtf and bi_igtf >= record.amount_total:
                        record.bi_igtf = min(record.bi_igtf + bi_igtf, record.amount_total)
                        bi_igtf = 0
                        continue
                    elif initial_residual <= bi_igtf:
                        record.bi_igtf = initial_residual
                        continue
                    record.bi_igtf = min(record.bi_igtf + bi_igtf, record.amount_total)
                    continue
        _logger.info(f'record.bi_igtf === {record.bi_igtf}')
        # _logger.info(xd.xd)

    def remove_igtf_from_move(self, partial_id):
        """Remove IGTF from move

        this method is called when a partial reconciliation is removed from the reconciliation widget
        search for the partial reconciliation and remove the IGTF from the move if it is a payment

        :param partial_id: id of the partial reconciliation to remove
        :type partial_id: int
        """
        _logger.warning(f'Removing IGTF from move for partial {partial_id}')
        partial = self.env["account.partial.reconcile"].browse(partial_id)

        payment_credit = partial.credit_move_id.payment_id
        payment_debit = partial.debit_move_id.payment_id

        move_credit = partial.credit_move_id.payment_id.reconciled_invoice_ids
        move_debit = partial.debit_move_id.payment_id.reconciled_invoice_ids

        reverse_move_credit = partial.credit_move_id.payment_id.reconciled_bill_ids
        reverse_move_debit = partial.debit_move_id.payment_id.reconciled_bill_ids

        for move in move_credit:
            if (
                payment_credit.is_igtf_on_foreign_exchange
                and move
                and move.bi_igtf > 0
            ):
                amount = partial.credit_move_id.payment_id.amount
                if self.env.company.currency_id.id == self.env.ref("base.VEF").id:
                    amount = amount * move.foreign_rate
                result = move.bi_igtf - amount
                if self.env.company.currency_id.id == self.env.ref("base.VEF").id:
                    result = move.bi_igtf - (amount * self.foreign_rate)
                if result < 0:
                    result = 0
                move.write({"bi_igtf": result})

        for move in move_debit:
            if (
                payment_debit.is_igtf_on_foreign_exchange
                and move
                and move.bi_igtf > 0
            ):
                amount = partial.debit_move_id.payment_id.amount
                if self.env.company.currency_id.id == self.env.ref("base.VEF").id:
                    amount = amount * move.foreign_rate
                result = move.bi_igtf - amount
                if self.env.company.currency_id.id == self.env.ref("base.VEF").id:
                    result = move.bi_igtf - (amount * self.foreign_rate)
                if result < 0:
                    result = 0
                move.write({"bi_igtf": result})

        for reverse_credit in reverse_move_credit:
            if (

                payment_credit.is_igtf_on_foreign_exchange
                and reverse_credit
                and reverse_credit.bi_igtf > 0
            ):
                amount = partial.credit_move_id.payment_id.amount
                if self.env.company.currency_id.id == self.env.ref("base.VEF").id:
                    amount = amount * reverse_credit.foreign_rate
                result = reverse_credit.bi_igtf - amount
                if self.env.company.currency_id.id == self.env.ref("base.VEF").id:
                    result = reverse_credit.bi_igtf - (amount * self.foreign_rate)
                if result < 0:
                    result = 0
                reverse_credit.write({"bi_igtf": result})

        for reverse_debit in reverse_move_debit:
            if (
                
                payment_debit.is_igtf_on_foreign_exchange
                and reverse_debit
                and reverse_debit.bi_igtf > 0
            ):
                amount = partial.debit_move_id.payment_id.amount
                if self.env.company.currency_id.id == self.env.ref("base.VEF").id:
                    amount = amount * reverse_debit.foreign_rate
                result = reverse_debit.bi_igtf - amount
                if self.env.company.currency_id.id == self.env.ref("base.VEF").id:
                    result = reverse_debit.bi_igtf - (amount * self.foreign_rate)
                if result < 0:
                    result = 0
                reverse_debit.write({"bi_igtf": result})

    def js_remove_outstanding_partial(self, partial_id):
        for move in self:
            move.remove_igtf_from_move(partial_id)

        # amount_residual = self.amount_residual
        # self.recalculate_bi_igtf(
        #     partial_id,
        #     initial_residual=amount_residual
        #     if not self.currency_id.is_zero(amount_residual)
        #     else self.amount_residual,

        # )
        res = super().js_remove_outstanding_partial(partial_id)
        return res

    def js_assign_outstanding_line(self, line_id):
        _logger.info('entrando a l10 igtf')
        amount_residual = self.amount_residual
        self = self.with_context(from_widget=True)
        res = super().js_assign_outstanding_line(line_id)
        self.recalculate_bi_igtf(
            line_id,
            initial_residual=amount_residual
            if not self.currency_id.is_zero(amount_residual)
            else self.amount_residual,
        )
        return res

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
            
            amount = rec.amount_total
            if rec.company_currency_id == self.env.ref("base.VEF"):
                    
                amount = rec.foreign_total_billed
            rec.igtf_top_aply = rec.company_currency_id.round((amount * (self.company_id.igtf_percentage / 100)))
            
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
                igtf_amount = 0.0
                igtf_line = payment_move.line_ids.filtered(lambda line: line.account_id.id in account)
                bank_line = payment_move.line_ids.filtered(lambda line: line.account_id.account_type in ['asset_cash'])
                cxc = [payment_move.partner_id.property_account_receivable_id.id, payment_move.partner_id.property_account_payable_id.id]
                cxc_line = payment_move.line_ids.filtered(lambda line: line.account_id.id in cxc)

                if bank_line:
                    if bank_line[0].company_currency_id == self.env.ref("base.VEF"):
                        bank_amount = abs(bank_line[0].foreign_balance) 
                    else:
                        bank_amount = abs(bank_line[0].balance)

                if cxc_line:
                    if cxc_line[0].company_currency_id == self.env.ref("base.VEF"):
                        cxc_amount = abs(cxc_line[0].foreign_balance) 
                    else:
                        cxc_amount = abs(cxc_line[0].balance)

                if igtf_line:
                    if igtf_line[0].company_currency_id == self.env.ref("base.VEF"):
                        igtf_amount = abs(igtf_line[0].foreign_balance) 
                    else:
                        igtf_amount = abs(igtf_line[0].balance)

  
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
            
            apply = rec.igtf_top_aply - (igtf_top * (rec.company_id.igtf_percentage / 100))
            rec.write({
                'igtf_top_aply': apply,
                'alter_bi_igtf': alter_bi_igtf
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
