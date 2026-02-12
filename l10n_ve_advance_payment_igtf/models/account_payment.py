from odoo import api, models, fields, _, Command
from odoo.exceptions import UserError
from odoo.tools import float_is_zero , float_compare
from odoo.tools import SQL

import logging

_logger = logging.getLogger(__name__)


class AccountPaymentAndIgtf(models.Model):
    _inherit = "account.payment"

    is_advance_payment = fields.Boolean(
        help="Check this box if this payment is an advance payment",
    )

    advanced_move_ids = fields.One2many(
        "account.move",
        "origin_payment_advanced_payment_id",
        string="Asientos de Anticipo",
        domain="[('move_type', '=', 'entry'), ('state', 'not in', ('draft', 'cancel'))]",
        help="Anticipos (account.move) aplicados a este pago.",
        copy=False,
    )

    is_igtf_on_foreign_exchange = fields.Boolean(
        string="IGTF on Foreign Exchange?",
        help="IGTF on Foreign Exchange",
        compute="_compute_is_igtf",
        store=True,
    )

    igtf_percentage = fields.Float(
        string="IGTF Percentage",
        compute="_compute_igtf_percentage",
        help="IGTF Percentage",
        store=True,
    )

    igtf_amount = fields.Float(
        string="IGTF Amount",
        help="IGTF Amount",
    )

    payment_from_wizard = fields.Boolean()
                
    @api.onchange('journal_id','destination_account_id')
    def _onchange_journal_id(self):
       for rec in self:
            customer_account = rec.company_id.advance_customer_account_id.id
            supplier_account = rec.company_id.advance_supplier_account_id.id
            if rec.journal_id and rec.journal_id.is_igtf:
                if rec.destination_account_id.id not in [customer_account, supplier_account]:
                    raise UserError(
                        _(
                            "The selected journal is configured for IGTF and fiscal, so the destination account must be either the advance customer account or the advance supplier account."
                        ))

    @api.depends(
        "journal_id", "partner_id", "partner_type",  "is_advance_payment"
    )
    def _compute_destination_account_id(self):

        for payment in self:

            customer_account = payment.company_id.advance_customer_account_id.id
            supplier_account = payment.company_id.advance_supplier_account_id.id

            if not customer_account or not supplier_account:
                raise UserError(
                    _(
                        "You must configure the advance customer account and the advance supplier account in the company settings"
                    )
                )

            if payment.is_advance_payment:
                if payment.partner_type == "customer":
                    payment.destination_account_id = customer_account
                    return
                elif payment.partner_type == "supplier":
                    payment.destination_account_id = supplier_account
                    return
            
            return super(AccountPaymentAndIgtf, self)._compute_destination_account_id()

    def _seek_for_lines(self):
        """Helper used to dispatch the journal items between:
        - The lines using the temporary liquidity account.
        - The lines using the counterpart account.
        - The lines being the write-off lines.
        :return: (liquidity_lines, counterpart_lines, writeoff_lines)

        this method is overriden to allow the use of advance payment accounts in counterpart lines
        the counterpart lines are the lines that are not liquidity lines and not writeoff lines

        """
        self.ensure_one()

        liquidity_lines = self.env["account.move.line"]
        counterpart_lines = self.env["account.move.line"]
        writeoff_lines = self.env["account.move.line"]

        for line in self.move_id.line_ids:
            if line.account_id in self._get_valid_liquidity_accounts():
                liquidity_lines += line

            elif (
                line.account_id.account_type in ("asset_receivable", "liability_payable", "liability_current", "asset_current")
                or line.partner_id == line.company_id.partner_id
            ):
                counterpart_lines = line

            else:
                writeoff_lines += line

        return liquidity_lines, counterpart_lines, writeoff_lines

    def _synchronize_from_moves(self, changed_fields):
        """Update the account.payment regarding its related account.move.
        Also, check both models are still consistent.
        :param changed_fields: A set containing all modified fields on account.move.


        this method is overriden to allow the use of advance payment accounts in counterpart lines
        now the counterpart lines allowed accounts types asset_current, that is the advance payment account type

        """
        if self._context.get("skip_account_move_synchronization"):
            return

        for pay in self.with_context(skip_account_move_synchronization=True):
            # After the migration to 14.0, the journal entry could be shared between the account.payment and the
            # account.bank.statement.line. In that case, the synchronization will only be made with the statement line.
            if pay.move_id.statement_line_id:
                continue

            move = pay.move_id
            move_vals_to_write = {}
            payment_vals_to_write = {}

            if "journal_id" in changed_fields:
                if pay.journal_id.type not in ("bank", "cash"):
                    raise UserError(_("A payment must always belongs to a bank or cash journal."))

            if "line_ids" in changed_fields:
                all_lines = move.line_ids
                liquidity_lines, counterpart_lines, writeoff_lines = pay._seek_for_lines()

                if len(liquidity_lines) != 1:
                    raise UserError(
                        _(
                            "Journal Entry %s is not valid. In order to proceed, the journal items must "
                            "include one and only one outstanding payments/receipts account.",
                            move.display_name,
                        )
                    )

                if len(counterpart_lines) != 1:
                    raise UserError(
                        _(
                            "Journal Entry %s is not valid. In order to proceed, the journal items must "
                            "include one and only one receivable/payable account (with an exception of "
                            "internal transfers).",
                            move.display_name,
                        )
                    )

                if any(line.currency_id != all_lines[0].currency_id for line in all_lines):
                    raise UserError(
                        _(
                            "Journal Entry %s is not valid. In order to proceed, the journal items must "
                            "share the same currency.",
                            move.display_name,
                        )
                    )

                if any(line.partner_id != all_lines[0].partner_id for line in all_lines):
                    raise UserError(
                        _(
                            "Journal Entry %s is not valid. In order to proceed, the journal items must "
                            "share the same partner.",
                            move.display_name,
                        )
                    )

                if (
                    counterpart_lines.account_id.account_type == "asset_receivable"
                    or counterpart_lines.account_id.account_type == "liability_current"
                ):
                    partner_type = "customer"
                else:
                    partner_type = "supplier"

                liquidity_amount = liquidity_lines.amount_currency

                move_vals_to_write.update(
                    {
                        "currency_id": liquidity_lines.currency_id.id,
                        "partner_id": liquidity_lines.partner_id.id,
                    }
                )
                payment_vals_to_write.update(
                    {
                        "amount": abs(liquidity_amount),
                        "partner_type": partner_type,
                        "currency_id": liquidity_lines.currency_id.id,
                        "partner_id": liquidity_lines.partner_id.id,
                    }
                )
                if liquidity_amount > 0.0:
                    payment_vals_to_write.update({"payment_type": "inbound"})
                elif liquidity_amount < 0.0:
                    payment_vals_to_write.update({"payment_type": "outbound"})

            move.write(move._cleanup_write_orm_values(move, move_vals_to_write))
            pay.write(move._cleanup_write_orm_values(pay, payment_vals_to_write))

    @api.depends("partner_id")
    def _compute_igtf_percentage(self):
        for payment in self:
            payment.igtf_percentage = payment.env.company.igtf_percentage

    @api.depends("journal_id")
    def _compute_is_igtf(self):
        for payment in self:
            payment.is_igtf_on_foreign_exchange = False
            if payment.journal_id.is_igtf and payment.journal_id.currency_id and payment.journal_id.currency_id != self.env.ref("base.VEF"):
                payment.is_igtf_on_foreign_exchange = True
                   
    def _prepare_move_line_default_vals(self, write_off_line_vals=None, force_balance=None):
       
        for rec in self:
            vals = super(AccountPaymentAndIgtf, self)._prepare_move_line_default_vals(
                write_off_line_vals,
                force_balance
            )
            if rec.payment_from_wizard:
                if rec.igtf_percentage and rec.igtf_amount:
                    rec._create_igtf_moves_in_payments(vals, write_off_line_vals)

            return vals

    def calculate_igtf_for_payment(self, invoice, amount_payment, payment_currency, base = False):
        
        currency = invoice.currency_id
        precision = currency.rounding
        
        due_currency_id = invoice.currency_id
        due_amount = self.convert_to_company_currency(due_currency_id, invoice.amount_residual,fields.Date.today())

        payment_amount = self.convert_to_company_currency(payment_currency, amount_payment,fields.Date.today())
        principal_debt = due_amount

        principal_amount = min(payment_amount, principal_debt)
        
        igtf_unrounded = principal_amount * (self.env.company.igtf_percentage / 100)

        igtf_top =  invoice.igtf_top_aply

        alter_bi_igtf = invoice.alter_bi_igtf

        igtf= igtf_unrounded

        invoice_residual = due_amount

    
        if not float_is_zero(igtf, precision_rounding=precision) and igtf_top == invoice_residual:
            
            return 0.0
        

        residual_igtf = igtf_top - alter_bi_igtf

        if float_compare(residual_igtf, 0.0, precision_rounding=precision) == 0.0:
            return 0.0
        
        if igtf > residual_igtf and  not float_is_zero(residual_igtf, precision_rounding=precision):
            
            igtf = residual_igtf

        if float_compare(igtf_top, 0.0, precision_rounding=precision) >= 0.0 and float_compare(igtf, igtf_top, precision_rounding=precision) > 0.0:
            
            return 0.0 
                
        if not base:
            return self.convert_to_external_currency(payment_currency, igtf, fields.Date.today())
        else:
            return igtf
    
    def convert_to_company_currency(self, from_currency,amount,date =False):
        """
        Convierte un monto desde una moneda específica a la moneda base de la compañía.
        """
        self.ensure_one()
        company_currency = self.company_id.currency_id
        
        if from_currency == company_currency:
            return amount

        converted_amount = from_currency._convert(
            amount, 
            company_currency, 
            self.company_id, 
            date or fields.Date.today()
        )
        
        return converted_amount
    
    def convert_to_external_currency(self, from_currency,amount,date =False):
     
        self.ensure_one()
        company_currency = self.company_id.currency_id
   
        converted_amount = company_currency._convert(
            amount, 
            from_currency, 
            self.company_id, 
            date or fields.Date.today()
        )
        
        return converted_amount
        
    def _create_igtf_moves_in_payments(self, vals, write_off_line_vals = False):
        
        igtf_account = (
            self.env.company.customer_account_igtf_id.id
            if self.partner_type == "customer"
            else self.env.company.supplier_account_igtf_id.id
        )

        if self._context.get("from_pos", False):
            return

        for payment in self:
            
            if payment.igtf_amount:
                if payment.payment_type == "inbound":
                    vals_igtf = [x for x in vals if x["account_id"] == igtf_account]

                    if not vals_igtf:
                        payment._prepare_inbound_move_line_igtf_vals(vals, write_off_line_vals)

                if payment.payment_type == "outbound":
                    vals_igtf = [x for x in vals if x["account_id"] == igtf_account]
                    if not vals_igtf:
                        payment._prepare_outbound_move_line_igtf_vals(vals,write_off_line_vals)

    def _create_inbound_move_line_igtf_vals(self, vals):
        
        for rec in self:
            currency = rec.currency_id 
            igtf_account = (
                self.env.company.customer_account_igtf_id.id
                if rec.partner_type == "customer"
                else self.env.company.supplier_account_igtf_id.id
            )
            igtf_amount = rec.igtf_amount
            account_id = igtf_account if rec.igtf_percentage else None
            
            precision = currency.rounding
            if float_compare(igtf_amount, 0.0, precision_rounding=precision) > 0.0:
                
                vals.append(
                    {
                        "name": "IGTF",
                        "currency_id": rec.currency_id.id,
                        "amount_currency": -igtf_amount,
                        "account_id": account_id,
                        "partner_id": rec.partner_id.id,
                    }
                )



        return vals

    def _create_outbound_move_line_igtf_vals(self, vals):
        
        for rec in self:
            igtf_account = (
                self.env.company.customer_account_igtf_id.id
                if rec.partner_type == "customer"
                else self.env.company.supplier_account_igtf_id.id
            )
            igtf_amount = rec.igtf_amount
            account_id = igtf_account if rec.igtf_percentage else None
            currency = self.currency_id 
            precision = currency.rounding
            if float_compare(igtf_amount, 0.0, precision_rounding=precision) > 0.0:
               
                vals.append(
                    {
                        "name": "IGTF",
                        "currency_id": rec.currency_id.id,
                        "amount_currency": igtf_amount,
                        "account_id": account_id,
                        "partner_id": rec.partner_id.id,
                    }
                )

        return vals
    
    def get_moves(self):
        """ Return the moves to pay from the context.
        Overridden to ensure that we always get the moves from the context,
        even if we are in edit mode.
        """

        ctx = self.env.context
        ids = ctx.get('active_ids', [])
        if not ids and ctx.get('active_id'):
            ids = [ctx.get('active_id')]
  
        # Validamos el modelo para no buscar IDs de factura en la tabla de líneas
        active_model = ctx.get('active_model', 'account.move')
        
        if active_model == 'account.move':
            return self.env["account.move"].browse(ids)
        else:
            # Si son líneas, obtenemos sus facturas
            move_lines = self.env["account.move.line"].browse(ids)
            return set(move_lines.mapped("move_id"))

    def _prepare_inbound_move_line_igtf_vals(self, vals, write_off_line_vals = False):
    
        for rec in self:
            lines = [line for line in vals]
            if rec.payment_type == "inbound":

                currency = rec.currency_id 
                precision = currency.rounding

                credit_line_unrounded = lines[1]["amount_currency"] + rec.igtf_amount
                credit_line = credit_line_unrounded
                credit_amount = self.convert_to_company_currency(currency,-credit_line)
                
                if float_compare(rec.igtf_amount, 0.0, precision_rounding=precision) > 0.0:
                    if not write_off_line_vals:
                        vals[1].update({"amount_currency": credit_line, "credit": credit_amount})
                
                if write_off_line_vals:
                    actual_value = vals[2]["amount_currency"] + rec.igtf_amount
                    vals[2].update({"amount_currency": actual_value, "balance": actual_value})

                rec._create_inbound_move_line_igtf_vals(vals)
                
    def _prepare_outbound_move_line_igtf_vals(self, vals,write_off_line_vals =False):
        
        for rec in self:
            lines = [line for line in vals]
            if rec.payment_type == "outbound":
                
                currency = rec.currency_id
                precision = currency.rounding

                debit_line_unrounded = lines[1]["amount_currency"] - rec.igtf_amount
                debit_line = debit_line_unrounded
                debit_amount = self.convert_to_company_currency(currency,debit_line)
                
                if float_compare(rec.igtf_amount, 0.0, precision_rounding=precision) > 0.0:
                    if not write_off_line_vals:
                        vals[1].update({"amount_currency": debit_line, "debit": debit_amount})

                if write_off_line_vals:
                    actual_value = vals[2]["amount_currency"] - rec.igtf_amount
                    vals[2].update({"amount_currency": actual_value, "balance": actual_value})

                rec._create_outbound_move_line_igtf_vals(vals)

    @api.depends('journal_id')
    def _compute_is_igtf_journal(self):
        for record in self:
            if record.journal_id.currency_id and record.journal_id.currency_id == self.env.ref("base.USD"):
                record.is_igtf_on_foreign_exchange = True
            else:
                record.is_igtf_on_foreign_exchange = False

    def action_cancel(self):
        for record in self:
            if record.advanced_move_ids:
                if record.advanced_move_ids and not self.env.context.get("move_action_cancel_advance_payment"):
                    return {
                        "name": "Alerta",
                        "type": "ir.actions.act_window",
                        "res_model": "move.action.cancel.advance.payment.wizard",
                        "views": [[False, "form"]],
                        "target": "new",
                        "context": {
                            "default_move_id": record.move_id.id,
                            "default_cross_move_ids": record.advanced_move_ids.ids,
                            "default_payment_id": record.id if record else False,
                            "default_partial_id": False,
                        },
                    }
            
            return super(AccountPaymentAndIgtf, self).action_cancel()

    def action_draft(self):
        for record in self:
            if record.advanced_move_ids:
                if record.advanced_move_ids and not self.env.context.get("move_action_cancel_advance_payment"):
                    return {
                        "name": "Alerta",
                        "type": "ir.actions.act_window",
                        "res_model": "move.action.cancel.advance.payment.wizard",
                        "views": [[False, "form"]],
                        "target": "new",
                        "context": {
                            "default_move_id": record.move_id.id,
                            "default_cross_move_ids": record.advanced_move_ids.ids,
                            "default_payment_id": record.id if record else False,
                            "default_partial_id": False,
                        },
                    }
            partial_id = False
            move_lines = record.move_id.line_ids
            partial_rec = (move_lines.matched_debit_ids | move_lines.matched_credit_ids)[:1]
            if partial_rec:
                partial_id = partial_rec.id
                
            if partial_id:
                record.move_id.remove_igtf_from_account_move(partial_id)
                record.move_id.line_ids.remove_move_reconcile()
            return super(AccountPaymentAndIgtf, self).action_draft()
    
    #Overrida
    @api.depends('move_id.line_ids.matched_debit_ids', 'move_id.line_ids.matched_credit_ids')
    def _compute_stat_buttons_from_reconciliation(self):
        ''' Retrieve the invoices reconciled to the payments through the reconciliation (account.partial.reconcile). '''
        stored_payments = self.filtered('id')
        if not stored_payments:
            self.reconciled_invoice_ids = False
            self.reconciled_invoices_count = 0
            self.reconciled_invoices_type = False
            self.reconciled_bill_ids = False
            self.reconciled_bills_count = 0
            self.reconciled_statement_line_ids = False
            self.reconciled_statement_lines_count = 0
            return

        self.env['account.payment'].flush_model(fnames=['move_id', 'outstanding_account_id'])
        self.env['account.move'].flush_model(fnames=['move_type', 'origin_payment_id', 'statement_line_id'])
        self.env['account.move.line'].flush_model(fnames=['move_id', 'account_id', 'statement_line_id'])
        self.env['account.partial.reconcile'].flush_model(fnames=['debit_move_id', 'credit_move_id'])

        self.env.cr.execute('''
            SELECT
                payment.id,
                ARRAY_AGG(DISTINCT invoice.id) AS invoice_ids,
                invoice.move_type
            FROM account_payment payment
            JOIN account_move move ON move.id = payment.move_id
            JOIN account_move_line line ON line.move_id = move.id
            JOIN account_partial_reconcile part ON
                part.debit_move_id = line.id
                OR
                part.credit_move_id = line.id
            JOIN account_move_line counterpart_line ON
                part.debit_move_id = counterpart_line.id
                OR
                part.credit_move_id = counterpart_line.id
            JOIN account_move invoice ON invoice.id = counterpart_line.move_id
            JOIN account_account account ON account.id = line.account_id
            WHERE account.account_type IN ('asset_receivable', 'liability_payable')
                AND payment.id IN %(payment_ids)s
                AND line.id != counterpart_line.id
                AND invoice.move_type in ('out_invoice', 'out_refund', 'in_invoice', 'in_refund', 'out_receipt', 'in_receipt')
            GROUP BY payment.id, invoice.move_type
        ''', {
            'payment_ids': tuple(stored_payments.ids)
        })
        query_res = self.env.cr.dictfetchall()

        for pay in self:
            
            pay.reconciled_invoice_ids = pay.invoice_ids.filtered(lambda m: m.is_sale_document(True))
            pay.reconciled_bill_ids = pay.invoice_ids.filtered(lambda m: m.is_purchase_document(True))

        if not query_res:
            self.reconciled_invoice_ids = False
            self.reconciled_invoices_count = 0
            self.reconciled_invoices_type = False
            self.reconciled_bill_ids = False
            self.reconciled_bills_count = 0
            self.reconciled_statement_line_ids = False
            self.reconciled_statement_lines_count = 0
            return
        
        for res in query_res:
            pay = self.browse(res['id'])
            
            if res['move_type'] in self.env['account.move'].get_sale_types(True):
                value = self.env['account.move'].browse(res.get('invoice_ids', []))
                
                pay.reconciled_invoice_ids |= self.env['account.move'].browse(res.get('invoice_ids', []))
            else:
                pay.reconciled_bill_ids |= self.env['account.move'].browse(res.get('invoice_ids', []))

        for pay in self:
            pay.reconciled_invoices_count = len(pay.reconciled_invoice_ids)
            pay.reconciled_bills_count = len(pay.reconciled_bill_ids)

        query_res = dict(self.env.execute_query(SQL('''
            SELECT
                payment.id,
                ARRAY_AGG(DISTINCT counterpart_line.statement_line_id) AS statement_line_ids
            FROM account_payment payment
            JOIN account_move move ON move.id = payment.move_id
            JOIN account_move_line line ON line.move_id = move.id
            JOIN account_account account ON account.id = line.account_id
            JOIN account_partial_reconcile part ON
                part.debit_move_id = line.id
                OR
                part.credit_move_id = line.id
            JOIN account_move_line counterpart_line ON
                part.debit_move_id = counterpart_line.id
                OR
                part.credit_move_id = counterpart_line.id
            WHERE account.id = payment.outstanding_account_id
                AND payment.id IN %(payment_ids)s
                AND line.id != counterpart_line.id
                AND counterpart_line.statement_line_id IS NOT NULL
            GROUP BY payment.id
        ''', payment_ids=tuple(stored_payments.ids)
        )))

        for pay in self:
            statement_line_ids = query_res.get(pay.id, [])
            pay.reconciled_statement_line_ids = [Command.set(statement_line_ids)]
            pay.reconciled_statement_lines_count = len(statement_line_ids)
            if len(pay.reconciled_invoice_ids.mapped('move_type')) == 1 and pay.reconciled_invoice_ids[0].move_type == 'out_refund':
                pay.reconciled_invoices_type = 'credit_note'
            else:
                pay.reconciled_invoices_type = 'invoice'