from odoo import api, fields, models,  Command, _
from odoo.tools.sql import column_exists, create_column
from odoo.tools import  float_compare, formatLang ,float_repr
from odoo.exceptions import UserError

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

    is_advance_move = fields.Boolean(
        string="Is Advance Move?",
        store=True,
    )

    igtf_top_aply = fields.Float('Max Igtf amount to be apply', copy=False)
    alter_bi_igtf = fields.Float('IGTF Apply',copy=False)
    foreign_bi_igtf = fields.Float('Foreigh Base imp Igtf',copy=False)

    invoice_outstanding_credits_debits_widget_advance_payment = fields.Binary(
        compute="_compute_payments_widget_to_reconcile_info_advance_payment",
    )
    origin_payment_advanced_payment_id = fields.Many2one("account.payment",copy=False)
    @api.depends(
        "bi_igtf",
    )
    def _compute_tax_totals(self):
        return super()._compute_tax_totals()

    @api.depends('invoice_outstanding_credits_debits_widget', 'invoice_outstanding_credits_debits_widget_advance_payment')
    def _compute_invoice_has_outstanding(self):
        #override
        # Primero ejecutamos la lógica original de Odoo
        super()._compute_invoice_has_outstanding()
        
        for move in self:
            # Si el super ya lo puso en True, lo dejamos en True.
            # Si está en False, revisamos nuestro nuevo campo.
            if not move.invoice_has_outstanding:
                move.invoice_has_outstanding = bool(move.invoice_outstanding_credits_debits_widget_advance_payment)


    #PAGOS y anticipos CONCILIADOS EN FACTURA
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
                    

                    reconciled_vals.append({
                        'name': counterpart_line.name,
                        'journal_name': counterpart_line.journal_id.name,
                        'company_name': counterpart_line.journal_id.company_id.name if counterpart_line.journal_id.company_id != move.company_id else False,
                        'amount': reconciled_partial['amount'],
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
    
    #PAGOS NO CONCILIADOS DE ANTICIPO
    def _compute_payments_widget_to_reconcile_info_advance_payment(self):
        for move in self:
            
            move.invoice_outstanding_credits_debits_widget_advance_payment = False

            if move.state != 'posted' \
                    or move.payment_state not in ('not_paid', 'partial') \
                    or not move.is_invoice(include_receipts=True):
                continue
            advance_accounts = False
            if move.move_type in ("out_invoice", "in_refund"):
                advance_accounts = self.env['account.account'].search([('is_advance_account', '=', True),('account_type','in',['liability_current'])])
            else:
                
                advance_accounts = self.env['account.account'].search([('is_advance_account', '=', True),('account_type','in',['asset_current'])])

            pay_term_lines = move.line_ids\
                .filtered(lambda line: line.account_id.account_type in ('asset_receivable', 'liability_payable') and  not line.account_id.is_advance_account)
            all_account_ids = (pay_term_lines.account_id | advance_accounts).ids

            domain = [
                ('account_id', 'in', all_account_ids),
                ('parent_state', '=', 'posted'),
                ('partner_id', '=', move.commercial_partner_id.id),
                ('reconciled', '=', False),
                '|', ('amount_residual', '!=', 0.0), ('amount_residual_currency', '!=', 0.0),
            ]
            
            payments_widget_vals = {'outstanding': True, 'content': [], 'move_id': move.id}

            if move.is_inbound():
                domain.append(('balance', '<', 0.0))
                payments_widget_vals['title'] = _('Anticipos')
            else:
                domain.append(('balance', '>', 0.0))
                payments_widget_vals['title'] = _('Anticipos')

            for line in self.env['account.move.line'].search(domain):
                if line.account_id.is_advance_account or line.payment_id_advance:
                    if line.currency_id == move.currency_id:
                        amount = abs(line.amount_residual_currency)
                    else:
                        
                        if line.currency_id.id == line.move_id.company_currency_id.id: ##pago VEF
                            
                            if line.date < move.invoice_date:
                                if line.payment_id.keep_alter_value_vef:
                                    
                                    amount = line.currency_id._convert(
                                        abs(line.amount_residual_currency),
                                        move.currency_id,
                                        move.company_id,
                                        line.date,
                                    )

                                else:
                                    amount = line.currency_id._convert(
                                        abs(line.amount_residual_currency),
                                        move.currency_id,
                                        move.company_id,
                                        move.invoice_date,
                                    )
                                    
                            else:
                                amount = line.currency_id._convert(
                                        abs(line.amount_residual_currency),
                                        move.currency_id,
                                        move.company_id,
                                        line.date,
                                    )
                                

                        else:
                            amount = move.company_currency_id._convert(
                                abs(line.amount_residual),
                                move.currency_id,
                                move.company_id,
                                line.date,
                            )

                    if move.currency_id.is_zero(amount):
                        continue

                    payments_widget_vals['content'].append({
                        'journal_name': line.ref or line.move_id.name,
                        "amount": amount,
                        "id": line.id,
                        "move_id": line.move_id.id,
                        "payment_id": line.payment_id.id,
                        "keep_alter_value_vef": line.payment_id.keep_alter_value_vef,
                        "position": move.currency_id.position,
                        "digits": [69, move.currency_id.decimal_places],
                        "payment_date": fields.Date.to_string(line.date),
                        "currency_id": move.currency_id.id,
                        "amount_residual_currency":abs(line.amount_residual_currency)
                        
                    })
            
            if not payments_widget_vals['content']:
                continue

            move.invoice_outstanding_credits_debits_widget_advance_payment = payments_widget_vals

    #Pagos no CONCILIADOS
    @api.depends('move_type', 'line_ids.amount_residual')
    def _compute_payments_widget_to_reconcile_info(self):
        super()._compute_payments_widget_to_reconcile_info()

        for move in self:
            move.invoice_outstanding_credits_debits_widget  = False

            if move.state != 'posted' \
                    or move.payment_state not in ('not_paid', 'partial') \
                    or not move.is_invoice(include_receipts=True):
                continue
            
            pay_term_lines = move.line_ids\
                .filtered(lambda line: line.account_id.account_type in ('asset_receivable', 'liability_payable') and  not line.account_id.is_advance_account)

            domain = [
                ('account_id', 'in', pay_term_lines.account_id.ids),
                ('parent_state', '=', 'posted'),
                ('partner_id', '=', move.commercial_partner_id.id),
                ('reconciled', '=', False),
                '|', ('amount_residual', '!=', 0.0), ('amount_residual_currency', '!=', 0.0),
            ]
            
            payments_widget_vals = {'outstanding': True, 'content': [], 'move_id': move.id}

            if move.is_inbound():
                domain.append(('balance', '<', 0.0))
                payments_widget_vals['title'] = _('Outstanding credits')
            else:
                domain.append(('balance', '>', 0.0))
                payments_widget_vals['title'] = _('Outstanding debits')

            for line in self.env['account.move.line'].search(domain):
                
                if not line.account_id.is_advance_account and not line.move_id.is_advance_move:
                    amount = False
                    if line.currency_id == move.currency_id:
                        amount = abs(line.amount_residual_currency)
                    else:
                        
                        if line.currency_id.id == line.move_id.company_currency_id.id: ##pago VEF
                            
                            if line.date < move.invoice_date:
                                if line.payment_id.keep_alter_value_vef:
                                    
                                    amount = line.currency_id._convert(
                                        abs(line.amount_residual_currency),
                                        move.currency_id,
                                        move.company_id,
                                        line.date,
                                    )

                                else:
                                    amount = line.currency_id._convert(
                                        abs(line.amount_residual_currency),
                                        move.currency_id,
                                        move.company_id,
                                        move.invoice_date,
                                    )
                                    
                            else:
                                amount = line.currency_id._convert(
                                        abs(line.amount_residual_currency),
                                        move.currency_id,
                                        move.company_id,
                                        line.date,
                                    )
                                

                        else:
                            amount = move.company_currency_id._convert(
                                abs(line.amount_residual),
                                move.currency_id,
                                move.company_id,
                                line.date,
                            )
                            
                                                      
                    if move.currency_id.is_zero(amount):
                        continue
                            

                    payments_widget_vals['content'].append({
                        "journal_name": line.ref or line.move_id.name,
                        "amount": amount,
                        "id": line.id,
                        "move_id": line.move_id.id,
                        "payment_id": line.payment_id.id,
                        "keep_alter_value_vef": line.payment_id.keep_alter_value_vef,
                        "position": move.currency_id.position,
                        "digits": [69, move.currency_id.decimal_places],
                        "payment_date": fields.Date.to_string(line.date),
                        "currency_id": move.currency_id.id,
                        "amount_residual_currency":abs(line.amount_residual_currency)
                    })


            if not payments_widget_vals["content"]:
                continue

            move.invoice_outstanding_credits_debits_widget = payments_widget_vals
    
    def _create_advance_payment_move(self, amount_residual, lines):
        self.ensure_one()
        advance_amount = 0.0
        advance_widget_value = getattr(self, 'invoice_outstanding_credits_debits_widget_advance_payment', False)
        advance_widget = advance_widget_value if isinstance(advance_widget_value, dict) else {} 
        widget_content = advance_widget.get('content') or []   
        
        advance_amount = next(
            (content.get('amount') for content in widget_content if content.get('move_id') == lines.move_id.id),
            0.0
        ) 

        amount_residual_currency = next(
            (content.get('amount_residual_currency') for content in widget_content if content.get('move_id') == lines.move_id.id),
            0.0
        ) 

        if not advance_amount or advance_amount == 0.0:
            raise UserError(_('The advance amount to apply was not found.'))            
       
        payment = lines.move_id.origin_payment_advanced_payment_id or lines.move_id.origin_payment_id
        
        if not payment:
            raise UserError(_('No associated Payment record found.'))
        is_customer = self.move_type in ["out_invoice", "in_refund"]
        
        receivable_payable_line = self.line_ids.filtered(
            lambda l: l.account_id.account_type in ("asset_receivable", "liability_payable")
        )
        if not receivable_payable_line:
            raise UserError(_('No accounts receivable/payable line found on the invoice.'))            
        account_rp = receivable_payable_line.account_id.id
        
      
        igtf_amount = 0.0
        is_igtf_journal = (
            payment.journal_id.is_igtf
            if (
                self.partner_id._check_igtf_apply_improved(self.move_type)
                and not self.journal_id.is_purchase_international
            )
            else False
        )
        base_amount_applied = 0.0

        base_amount_residual = self.amount_residual 

        date_conver = False
        if payment.date <= self.invoice_date:
            date_conver = self.invoice_date
        else:
            date_conver = payment.date

        amount_residual = self.currency_id._convert(
            base_amount_residual, 
            payment.currency_id, 
            self.company_id, 
            date_conver,
            round = False
        )

        if payment.currency_id != self.currency_id :
            if payment.currency_id == self.company_id.currency_id and payment.keep_alter_value_vef:

                date_conver = payment.date
                advance_amount = self.currency_id._convert(
                    advance_amount, 
                    payment.currency_id, 
                    self.company_id, 
                    date_conver,
                    round = True
                )
            
            else:

                advance_amount = amount_residual_currency

        if is_igtf_journal:
            igtf_amount = abs(payment.calculate_igtf_for_payment(self, advance_amount,  payment.currency_id ,date_conver))
           
            
        base_amount_applied = min(amount_residual, advance_amount)

        amount_line1 = base_amount_applied

        amount_line2 = amount_line1 + igtf_amount 

        line_2 = 'credit' if is_customer else 'debit'
        igtf_line = line_2
        
        if is_customer:
            if  advance_amount > amount_residual + igtf_amount and is_igtf_journal:

                base_amount_applied = amount_residual + igtf_amount
                amount_line1 = base_amount_applied#ant/banck
                amount_line2 = amount_residual  # cxc
               
            elif advance_amount < amount_residual + igtf_amount and is_igtf_journal:

                amount_line1 = (advance_amount) #bank/ant
                amount_line2 = (advance_amount - igtf_amount)  # cxc


            elif  advance_amount == amount_residual + igtf_amount and is_igtf_journal:
                
                amount_line1 = advance_amount #bank/ant
                amount_line2 = amount_residual # cxc

             
            else:
                line_2 = 'credit'
        else:

            if  advance_amount > amount_residual + igtf_amount and is_igtf_journal:
                base_amount_applied = amount_residual + igtf_amount
                amount_line1 = base_amount_applied
                amount_line2 = amount_residual  # cxc

            elif advance_amount < amount_residual + igtf_amount and is_igtf_journal:

                amount_line1 = (advance_amount) #bank/ant
                amount_line2 = (advance_amount - igtf_amount)  # cxc

            elif  advance_amount == amount_residual + igtf_amount and is_igtf_journal:
                
                amount_line1 = advance_amount #bank/ant
                amount_line2 = amount_residual  # cxc
        
            else:
                line_2 = 'debit'

        def _to_vef(amount):
            
            return payment.currency_id._convert(
                amount, self.company_currency_id, self.company_id, date_conver,round=False
            )
        
        vef_line1 = payment.currency_id.round(_to_vef(amount_line1))
        vef_line2 = payment.currency_id.round(_to_vef(amount_line2))

        if abs(vef_line1) > abs(self.amount_residual_signed) and self.invoice_date == payment.date:
            vef_line2 = abs(self.amount_residual_signed)

        vef_igtf = abs(vef_line1) - abs(vef_line2)
        vef_igtf = float(float_repr(vef_igtf, precision_digits= payment.currency_id.decimal_places))

        amount_currency_igtf = abs(amount_line1) - abs(amount_line2)
        if is_customer:
            amount_line2 = -amount_line2 if line_2 == 'credit' else amount_line2
            amount_line1 = amount_line1 
            amount_currency_igtf = -amount_currency_igtf if igtf_line == 'credit' else amount_currency_igtf
        else:
            
            amount_line2 = amount_line2 if line_2 == 'debit' else -amount_line2
            amount_line1 = -amount_line1
            amount_currency_igtf = -amount_currency_igtf if igtf_line == 'credit' else amount_currency_igtf
        

        # --- Configuración de Cuentas ---
        advance_line = lines.filtered_domain([
            '|',
                '&', ('account_id.account_type', '=', 'liability_current'), ('account_id.is_advance_account', '=', True),
                '&', ('account_id.account_type', '=', 'asset_current'), ('account_id.is_advance_account', '=', True),
            ('account_id.reconcile', '=', True)
        ])
        
        advance_line = advance_line.account_id[:1]

        if not advance_line:
            if is_customer: # O usa tu lógica de partner_type
                advance_line = self.partner_id.default_advance_customer_account_id
            else:
                advance_line = self.partner_id.default_advance_supplier_account_id
        
        if is_customer:
            name_rp, name_adv = "CUENTA POR COBRAR CLIENTE", "ANTICIPO/CLIENTE"
            account_adv = advance_line.id
            igtf_account = self.env.company.customer_account_igtf_id.id
        else:
            name_rp, name_adv = "CUENTA POR PAGAR PROVEEDOR", "ANTICIPO/PROVEEDOR"
            account_adv = advance_line.id
            igtf_account = self.env.company.supplier_account_igtf_id.id

        common_vals = {
            "partner_id": self.partner_id.id,
            "payment_id_advance": payment.id,
            "reconciled": False,
            "date": date_conver if not payment.keep_alter_value_vef else payment.date,
        }

        # --- Construcción de las Líneas ---
        line_vals = []

        # 1. Línea CxC / CxP
        line_vals.append(Command.create({
            "name": name_rp,
            "account_id": account_rp,
            "amount_currency": amount_line2,
            "currency_id": payment.currency_id.id,
            #line_2:vef_line2,
            **common_vals
        }))

        # 2. Línea Anticipo
        line_vals.append(Command.create({
            "name": name_adv,
            "account_id": account_adv,
            "amount_currency": amount_line1,
            "currency_id": payment.currency_id.id,
            #"debit": vef_line1 if is_customer else 0.0,
            #"credit": vef_line1 if not is_customer else 0.0,
            **common_vals
        }))

        # 3. Línea IGTF (Sólo si hay valor en VEF para evitar líneas en 0)
        if not self.company_currency_id.is_zero(vef_igtf) and is_igtf_journal:
            line_vals.append(Command.create({
                "name": "IGTF",
                "account_id": igtf_account,
                "amount_currency": amount_currency_igtf,
                "currency_id": payment.currency_id.id,
                #igtf_line:vef_igtf,
                **common_vals
            }))

        # --- Creación del Asiento ---
        advance_journal = self.env.company.advance_payment_igtf_journal_id
        
        return self.env["account.move"].create({
            "journal_id": advance_journal.id,
            "date": date_conver if not payment.keep_alter_value_vef else payment.date,
            "partner_id": self.partner_id.id,
            "ref": "CRUCE DE ANTICIPO (IGTF)",
            "line_ids": line_vals,
            "is_advance_move": True,
            "currency_id": payment.currency_id.id,
            "origin_payment_advanced_payment_id": payment.id, 
        })

    def _reconcile_move_with_payment_difference(self, payment_move, cross_move):
        """
        Realiza una doble conciliación entre un asiento de factura (self) y un asiento de cruce/pago (cross_move).

        El proceso concilia:
        1. Las líneas de Cuentas de Anticipo (Advance Account) para marcar el uso del anticipo.
        2. Las líneas de Cuentas por Cobrar/Pagar (A/R o A/P) para cerrar la deuda de la factura.

        :param account.move payment_move: El asiento de pago/anticipo original (ya no usado, se usa self.line_ids).
        :param account.move cross_move: El asiento de cruce de anticipo recién creado.
        :return: True si la conciliación fue exitosa.
        :rtype: bool
        """
        self.ensure_one()
        is_customer = False

        if self.move_type in ["out_invoice", "in_refund"]:
            is_customer = True
        elif self.move_type in ["in_invoice", "out_refund"]:
            is_customer = False
        else:
            return False 

        company = self.company_id
        self = self.with_company(company)
        cross_move = cross_move.with_company(company)
        cross_move.action_post()


        advance_line = payment_move.line_ids.filtered_domain([
            '|',
                '&', ('account_id.account_type', '=', 'liability_current'), ('account_id.is_advance_account', '=', True),
                '&', ('account_id.account_type', '=', 'asset_current'), ('account_id.is_advance_account', '=', True),
            ('account_id.reconcile', '=', True)
        ])

        advance_line = advance_line.account_id[:1]

        if not advance_line:
            
            if is_customer: # usa tu lógica de partner_type
                advance_line = self.partner_id.default_advance_customer_account_id
            else:
                advance_line = self.partner_id.default_advance_supplier_account_id
                

        original_advance_lines = payment_move.line_ids.filtered(
            lambda l: l.account_id.id == advance_line.id
        )
        cross_advance_lines = cross_move.line_ids.filtered(
            lambda l: l.account_id.id == advance_line.id
        )

        advance_lines_to_reconcile = original_advance_lines + cross_advance_lines

        for line in advance_lines_to_reconcile:
            if not line.date_maturity:
                line.date_maturity = line.date

                
        advance_lines_to_reconcile.reconcile()

        
        asset_types = ["asset_receivable", "liability_payable"]
        
        cross_rp_lines = cross_move.line_ids.filtered(
            lambda l: l.account_id.account_type in asset_types
        )
        
        invoice_rp_lines = self.line_ids.filtered(
            lambda l: l.account_id.account_type in asset_types
        )

        rp_lines_to_reconcile = cross_rp_lines + invoice_rp_lines

        for line in rp_lines_to_reconcile:
            if not line.date_maturity:
                line.date_maturity = line.date


        rp_lines_to_reconcile.reconcile()

        return True
    
    def js_assign_outstanding_line(self, line_id):
       

        self.ensure_one()

        outstanding_line = self.env["account.move.line"].browse(line_id)
        payment_move = outstanding_line.move_id
        
        
        is_advance_payment = payment_move.is_advance_move or payment_move.origin_payment_advanced_payment_id or (
            payment_move.origin_payment_id and payment_move.origin_payment_id.is_advance_payment
        )
        initial_residual = self.amount_residual_signed
        if is_advance_payment:
            
            
            move_to_reconcile = self._create_advance_payment_move(
                initial_residual, 
                outstanding_line
            ) 
            
            self._reconcile_move_with_payment_difference(
                outstanding_line.move_id, 
                move_to_reconcile
            )

            return

        
        return super().js_assign_outstanding_line(line_id)

    def js_remove_outstanding_partial(self, partial_id):
        self.ensure_one()

        partial = self.env["account.partial.reconcile"].browse(partial_id)
        partial_move_id = next((m for m in (partial.credit_move_id.move_id, partial.debit_move_id.move_id) if m.origin_payment_id or m.origin_payment_advanced_payment_id), None)
        move_credit = partial.credit_move_id.move_id
        move_debit = partial.debit_move_id.move_id
        
        payment_id = False
        if partial_move_id:
            payment_id = partial_move_id.origin_payment_id or partial_move_id.origin_payment_advanced_payment_id
      
        factura = None
        if move_credit.move_type in ['out_invoice', 'in_invoice']:
            factura = move_credit
        elif move_debit.move_type in ['out_invoice', 'in_invoice']:
            factura = move_debit



        if partial_move_id and payment_id.advanced_move_ids:
            cross_move_ids = payment_id.advanced_move_ids.filtered(lambda m: m.state not in ('draft', 'cancel')).ids
            if cross_move_ids and payment_id.move_id.id == partial_move_id.id:
                return {
                    "name": "Alerta",
                    "type": "ir.actions.act_window",
                    "res_model": "move.action.cancel.advance.payment.wizard",
                    "views": [[False, "form"]],
                    "target": "new",
                    "context": {
                        "default_move_id": factura.id,
                        "default_cross_move_ids": cross_move_ids,
                        "default_payment_id": payment_id.id if payment_id else False,
                        "default_partial_id": partial_id,
                    },
                }
            else:
                
                executed = self.remove_igtf_from_account_move(partial_id)
                partial = self.env["account.partial.reconcile"].browse(partial_id)
                if partial:
                    self.cancel_advance_payment_transaction(payment_id, partial_move_id)
                return
            
        executed = self.remove_igtf_from_account_move(partial_id)
        partial = self.env["account.partial.reconcile"].browse(partial_id)

        if not executed and partial:
            return super().js_remove_outstanding_partial(partial.id)
    
    def cancel_advance_payment_transaction(self, origin_payment_id, partial_reconcile):
        if not partial_reconcile:
            raise UserError(_("The partial reconciliation record is mandatory for cancellation."))        
        
        partial_reconcile.line_ids.remove_move_reconcile()
        partial_reconcile.button_draft()
        partial_reconcile.button_cancel()
        partial_reconcile.write({'origin_payment_advanced_payment_id': False})
        origin_payment_id.write({'advanced_move_ids': [(3, partial_reconcile.id)]})

    @api.depends('amount_residual')
    def compute_bi_igtf(self):
        for rec in self:
            if abs(rec.amount_total_signed) > 0 or rec.payment_state in ['paid','in_payment']: 
                rec.igtf_top_aply = abs(rec.amount_total_signed) * (self.company_id.igtf_percentage / 100)
                receivable_payable_lines = rec.line_ids.filtered(lambda line: line.account_id.reconcile)

                final_payment_moves = receivable_payable_lines.reconciled_lines_excluding_exchange_diff_ids.mapped('move_id')

                account = [rec.company_id.customer_account_igtf_id.id,rec.company_id.supplier_account_igtf_id.id ]
                
                total_bi_igtf = 0.0
                igtf_top = 0.0
                alter_bi_igtf = 0.0
                foreign_bi_igtf = 0.0
                bank_amount = 0.0

                target_account = False

                partial_amount = 0.0

                partner_context = rec.partner_id.with_company(rec.company_id)
                for payment_move in final_payment_moves:
                    igtf_line = payment_move.line_ids.filtered(lambda line: line.account_id.id in account)
                    bank_line = payment_move.line_ids.filtered(lambda line: line.account_id.account_type in ['asset_cash','asset_current','liability_current','asset_receivable'])
                    
                    bank_amount = 0.0
                    igtf_amount = 0.0
                    target_account = False
                    amount_base_payment = 0.0
                    if bank_line:

                        if rec.move_type in ['out_invoice', 'out_refund']:
                            target_account = partner_context.property_account_receivable_id
                        else:
                            target_account = partner_context.property_account_payable_id

                        factura_line = rec.line_ids.filtered(lambda l: l.account_id.id == target_account.id)

                        pago_line = payment_move.line_ids.filtered(lambda l: l.account_id.id == target_account.id)
                        
                        partial = self.env['account.partial.reconcile'].search([
                            '|',
                            '&', ('debit_move_id', '=', factura_line.id), ('credit_move_id', '=', pago_line.ids),
                            '&', ('debit_move_id', '=', pago_line.ids), ('credit_move_id', '=', factura_line.id)
                        ])
                        
                        if partial:
                            partial_amount = sum(partial.mapped('amount'))
                            bank_amount = partial_amount
                        
                        if igtf_line and partial:
                        
                            igtf_amount = abs(igtf_line[0].balance)
                            partial_amount = partial_amount
                            bank_amount = partial_amount
                        
                        if not igtf_line and bank_line and partial:
                            igtf_top += bank_amount
                            
                        

                        if igtf_line and bank_line and partial:
                            if payment_move.origin_payment_id and payment_move.origin_payment_id.reconciled_invoices_count > 1:

                                amount_base_payment = bank_amount

                            
                            elif (bank_amount * (rec.company_id.igtf_percentage / 100)) < igtf_amount:
                                if (bank_amount * (rec.company_id.igtf_percentage / 100)) == igtf_amount:
                                    
                                    amount_base_payment = bank_amount
                                else:
                                    
                                    amount_base_payment = igtf_amount / (rec.company_id.igtf_percentage / 100)
                                    
                                
                                if 'pos_payment_ids' in bank_line[0].move_id._fields:
                                    if bank_line[0].move_id.pos_payment_ids:
                                        amount_base_payment = igtf_amount / (rec.company_id.igtf_percentage / 100)
                            else:
                                
                                amount_base_payment = igtf_amount / (rec.company_id.igtf_percentage / 100)

                        if igtf_line and partial:
                            alter_bi_igtf += igtf_amount
                            
                    total_bi_igtf += amount_base_payment

                    date_conver = False
                    if payment_move.date <= rec.invoice_date:
                        date_conver = rec.invoice_date
                    else:
                        date_conver = payment_move.date

                    foreign_bi_igtf += rec.company_id.currency_id._convert(
                        amount_base_payment, 
                        rec.currency_id, 
                        rec.company_id, 
                        date_conver,
                        round = False
                    )
                
                
                apply = rec.igtf_top_aply - (igtf_top * (rec.company_id.igtf_percentage / 100))
                rec.igtf_top_aply = apply
                rec.alter_bi_igtf = alter_bi_igtf
                rec.foreign_bi_igtf = foreign_bi_igtf
                rec.bi_igtf = total_bi_igtf

    def remove_igtf_from_account_move(self, partial_id):

        partial_reconcile = self.env['account.partial.reconcile'].with_company(self.company_id).sudo().browse(partial_id).exists()
        
        related_moves = partial_reconcile.debit_move_id.move_id | partial_reconcile.credit_move_id.move_id
        
        igtf_account_ids = [
            self.company_id.customer_account_igtf_id.id,
            self.company_id.supplier_account_igtf_id.id
        ]

        not_search = [
            'out_invoice',
            'out_refund',
            'in_invoice',
            'in_refund',
            'out_receipt',
            'in_receipt',
        ]
        
        liquidity_account_types = ['asset_cash','bank','asset_current','liability_current']
        payment_move = related_moves.filtered(
            lambda move: move.line_ids.filtered(
                lambda line: line.account_id.account_type in liquidity_account_types and line.move_id.move_type not in not_search
            )
        )[:1]

        
        if not payment_move:
            return False
        if payment_move.currency_id == self.env.ref("base.VEF") and not payment_move.origin_payment_advanced_payment_id:
            return 
        

    
        try:
            payment_move.button_draft()
            
        except Exception:
            return False
        
        
        igtf_line = payment_move.line_ids.filtered(lambda line: line.account_id.id in igtf_account_ids)
        receivable_payable_line = payment_move.line_ids.filtered(
            lambda line: line.account_id.id in [payment_move.partner_id.property_account_payable_id.id,payment_move.partner_id.property_account_receivable_id.id ]
        )[:1]
        if igtf_line and receivable_payable_line:
            
            igtf_line_balance = igtf_line.balance

            current_debit = receivable_payable_line.debit
            current_credit = receivable_payable_line.credit
            new_lines_commands = []
            
            for line in payment_move.line_ids:

                if line.id == igtf_line.id:
                    new_lines_commands.append((2, line.id, False))
                    
                elif line.id == receivable_payable_line.id:
                    
                    current_debit = line.debit
                    current_credit = line.credit
                    current_balance = line.balance
                    current_f_balance = line.foreign_balance
                    current_amount_currency = line.amount_currency
                    current_f_debit = line.foreign_debit
                    current_f_credit = line.foreign_credit
                    
                    if igtf_line_balance > 0: # IGTF DÉBIT
                        new_debit = current_debit + igtf_line_balance
                        new_credit = 0.0
                        new_balance = current_balance + igtf_line.balance
                        new_f_balance = current_f_balance + igtf_line.foreign_balance
                        new_amount_currency = current_amount_currency + igtf_line.amount_currency
                        new_f_debit = current_f_debit + igtf_line.foreign_debit
                        new_f_credit = current_f_credit + igtf_line.foreign_credit
                      
                    else: # IGTF CRÉDIT
                        new_credit = current_credit + abs(igtf_line_balance)
                        new_debit = 0.0
                        new_balance = current_balance + igtf_line.balance
                        new_f_balance = current_f_balance + igtf_line.foreign_balance
                        new_amount_currency = current_amount_currency + igtf_line.amount_currency
                        new_f_debit = current_f_debit + igtf_line.foreign_debit
                        new_f_credit = current_f_credit + igtf_line.foreign_credit
                    
                    advance_account = payment_move.partner_id.default_advance_customer_account_id.id if current_credit > 0 else  payment_move.partner_id.default_advance_supplier_account_id.id
                    
                    line_vals = {
                        'debit': new_debit,
                        'credit': new_credit,
                        'balance': new_balance,
                        'amount_currency': new_amount_currency,
                        'foreign_balance':new_f_balance,
                        'foreign_debit':new_f_debit,
                        'foreign_credit':new_f_credit,
                        'account_id': advance_account if not payment_move.origin_payment_id.destination_account_id.is_advance_account else payment_move.origin_payment_id.destination_account_id.id,
                        'name': line.name,
                    }

                    new_lines_commands.append((1, line.id, line_vals))
                else:
                    new_lines_commands.append((1, line.id, {}))

            payment_move.write({
                'line_ids': new_lines_commands
            })

            if 'is_advance_payment' in payment_move.origin_payment_id._fields:

                if payment_move.origin_payment_id and not payment_move.origin_payment_id.is_advance_payment:

                    payment_move.origin_payment_id.write({
                        'is_advance_payment':True,
                        'igtf_amount': 0.0
                    })
            

            
        try:

            if payment_move.origin_payment_advanced_payment_id:
                payment_move.origin_payment_advanced_payment_id.write({'advanced_move_ids': [(3, payment_move.id)]})
                payment_move.button_cancel()
            else:
                payment_move.action_post()
        except Exception:
            return False
            
        return True
    

    def button_draft(self):
        """ Override Method to remove the reconciliation and set to draft the moves related to the advance payment when the invoice is reset to draft.
        """
        if any(move.state not in ('cancel', 'posted') for move in self):
            raise UserError(_("Only posted/cancelled journal entries can be reset to draft."))
        if any(move.need_cancel_request for move in self):
            raise UserError(_("You can't reset to draft those journal entries. You need to request a cancellation instead."))

        self._check_draftable()
        # We remove all the analytics entries for this journal
        self.line_ids.analytic_line_ids.with_context(skip_analytic_sync=True).unlink()
        self.mapped('line_ids').remove_move_reconcile()
        self.state = 'draft'
        self.sending_data = False

        self._detach_attachments()

      
