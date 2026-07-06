from odoo import api, fields, models,  Command, _
from odoo.tools.sql import column_exists, create_column
from odoo.tools import formatLang, float_repr
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

    igtf_top_aply = fields.Float('Max Igtf amount to be apply', copy=False, compute='compute_bi_igtf',store=True)
    alter_bi_igtf = fields.Float('IGTF Apply',copy=False ,compute='compute_bi_igtf',store=True)
    foreign_bi_igtf = fields.Float('Foreigh Base imp Igtf',copy=False, compute='compute_bi_igtf',store=True)

    invoice_outstanding_credits_debits_widget_advance_payment = fields.Binary(
        compute="_compute_payments_widget_to_reconcile_info_advance_payment",
    )
    origin_payment_advanced_payment_id = fields.Many2one("account.payment",copy=False)
 

    @api.depends('invoice_outstanding_credits_debits_widget', 'invoice_outstanding_credits_debits_widget_advance_payment')
    def _compute_invoice_has_outstanding(self):
        # override
        # First run Odoo's original logic
        super()._compute_invoice_has_outstanding()
        
        for move in self:
            # If super already set it to True, leave it as True.
            # If it is False, check our new field.
            if not move.invoice_has_outstanding:
                move.invoice_has_outstanding = bool(move.invoice_outstanding_credits_debits_widget_advance_payment)


    # RECONCILED PAYMENTS and advances ON INVOICE
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
    
    # UNRECONCILED ADVANCE PAYMENTS
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
                    date_to_convert = max(move.invoice_date, line.date)
                    if line.currency_id == move.currency_id:
                        amount = abs(line.amount_residual_currency)
                        date_to_convert = line.date
                    else:
                    
                        if line.currency_id.id == line.move_id.company_currency_id.id: ## VEF payment

                            if line.payment_id.keep_alter_value_vef: #Keep values in alternate currency for VEF payments
                                
                                amount = line.currency_id._convert(
                                    abs(line.amount_residual),
                                    move.currency_id,
                                    move.company_id,
                                    line.date,
                                )
                                date_to_convert = line.date


                            else:
                                amount = line.currency_id._convert( #Not Keep values in alternate currency for VEF payments
                                    abs(line.amount_residual_currency),
                                    move.currency_id,
                                    move.company_id,
                                    date_to_convert
                                )
                                
                        else: 
                            amount = line.currency_id._convert(
                                    abs(line.amount_residual),
                                    move.currency_id,
                                    move.company_id,
                                    date_to_convert
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
                        "amount_residual_currency":abs(line.amount_residual_currency),
                        "date_to_convert": date_to_convert
                        
                    })
            
            if not payments_widget_vals['content']:
                continue

            move.invoice_outstanding_credits_debits_widget_advance_payment = payments_widget_vals

    # Unreconciled Payments
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
                    date_to_convert = max(move.invoice_date, line.date)
                    if line.currency_id == move.currency_id:
                        amount = abs(line.amount_residual_currency)
                        date_to_convert = line.date
                    else:
                    
                        if line.currency_id.id == line.move_id.company_currency_id.id: ## VEF payment

                            if line.payment_id.keep_alter_value_vef: #Keep values in alternate currency for VEF payments
                                
                                amount = line.currency_id._convert(
                                    abs(line.amount_residual),
                                    move.currency_id,
                                    move.company_id,
                                    line.date,
                                )
                                date_to_convert = line.date


                            else:
                                amount = line.currency_id._convert( #Not Keep values in alternate currency for VEF payments
                                    abs(line.amount_residual_currency),
                                    move.currency_id,
                                    move.company_id,
                                    date_to_convert
                                )
                                
                        else: 
                            amount = line.currency_id._convert(
                                    abs(line.amount_residual),
                                    move.currency_id,
                                    move.company_id,
                                    date_to_convert
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
                        "amount_residual_currency":abs(line.amount_residual_currency),
                        "date_to_convert": date_to_convert
                    })


            if not payments_widget_vals["content"]:
                continue

            move.invoice_outstanding_credits_debits_widget = payments_widget_vals
    
    def _create_advance_payment_move(self, amount_residual, lines):
        self.ensure_one()
        advance_amount = 0.0
        widget = getattr(self, 'invoice_outstanding_credits_debits_widget_advance_payment', {}) or {}
        widget_content = widget.get('content', []) if isinstance(widget, dict) else []

        target_move_id = lines.move_id.id
        matched_content = next(
            (c for c in widget_content if c.get('move_id') == target_move_id), 
            None
        )
        
        advance_amount = matched_content.get('amount', 0.0) if matched_content else 0.0
        advance_amount_residual = matched_content.get('amount_residual_currency', 0.0) if matched_content else 0.0
        conversion_date = matched_content.get('date_to_convert') if matched_content else False

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
   
            
        base_amount_applied = min(amount_residual, advance_amount)

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
        
        advance_val = False
        counter_part_val = False
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
            "date": conversion_date,
        }

        advance_val = {
            "name": name_adv,
            "account_id": account_adv,
            }
        
        counter_part_val = {
            "name": name_rp,
            "account_id": account_rp,
        }   
        if is_igtf_journal:
            igtf_amount = abs(payment.calculate_igtf_for_payment(self, base_amount_applied,  payment.currency_id ,conversion_date))

        if is_igtf_journal:
            if (base_amount_applied + igtf_amount) < advance_amount: ## include igtf in base
                base_amount_applied = base_amount_applied + igtf_amount
                

        # --- Construcción de las Líneas base ---
        line_vals = self.prepare_advance_payment_vals(
            payment, base_amount_applied, advance_val, counter_part_val, conversion_date, common_vals,advance_amount_residual)
        
        if is_igtf_journal and igtf_amount > 0.0:

            line_vals = self.prepare_igtf_payment_vals(
                line_vals, payment, igtf_amount, igtf_account, conversion_date, common_vals
            )
               
        # --- Entry Creation ---
        advance_journal = self.env.company.advance_payment_igtf_journal_id
        
        return self.env["account.move"].create({
            "journal_id": advance_journal.id,
            "date": conversion_date if not payment.keep_alter_value_vef else payment.date,
            "partner_id": self.partner_id.id,
            "ref": "CRUCE DE ANTICIPO",
            "line_ids": line_vals,
            "is_advance_move": True,
            "currency_id": payment.currency_id.id,
            "origin_payment_advanced_payment_id": payment.id, 
        })

    def prepare_advance_payment_vals(self, payment , amount, advance_values, counter_part_values, date, common_vals,residual_amoun=False):
        self.ensure_one()
        amount_advance = 0.0
        sign = 1 if payment.payment_type == 'inbound' else -1
        amount_advance = amount * sign

        if payment.currency_id == self.company_id.currency_id:
            advance_balance = amount_advance
        else:
            
            advance_balance = self.currency_id._convert(
                amount_advance,  self.company_id.currency_id, self.company_id, date )  
            
        line_vals = []

        line_vals.append(Command.create({
            'name': advance_values['name'],
            'account_id': advance_values['account_id'],
            'currency_id': payment.currency_id.id,
            'balance': advance_balance,          # Línea principal
            'amount_currency': amount_advance,
            **common_vals
        }))

        line_vals.append(Command.create({
            'name': counter_part_values['name'],
            'account_id': counter_part_values['account_id'],
            'currency_id':  payment.currency_id.id,
            'balance': -advance_balance,
            'amount_currency': -amount_advance,
            **common_vals
        }))
        
        return line_vals
    
    def prepare_igtf_payment_vals(self, vals, payment, igtf_amount, igtf_account_id, date, common_vals):
        self.ensure_one()
    
        if payment.currency_id == self.company_currency_id:
            igtf_balance = igtf_amount
        else:
            igtf_balance = self.currency_id._convert(
                igtf_amount, self.company_currency_id, self.company_id, date
            )

        sign = -1 if payment.payment_type == 'inbound' else 1
        
        if isinstance(vals[1], tuple) and len(vals[1]) == 3:
            anticipo_dict = vals[1][2]
        else:
            anticipo_dict = vals[1]

        anticipo_dict.update({
            'amount_currency': anticipo_dict.get('amount_currency', 0.0) - (igtf_amount * sign),
            'balance': anticipo_dict.get('balance', 0.0) - (igtf_balance * sign)
        })


        total_balance_prev = 0.0
        total_amount_currency_prev = 0.0

        for line in vals:
            line_dict = line[2] if isinstance(line, tuple) and len(line) == 3 else line
            if isinstance(line_dict, dict):
                total_balance_prev += line_dict.get('balance', 0.0)
                total_amount_currency_prev += line_dict.get('amount_currency', 0.0)

        # El residual exacto que necesita Odoo para cerrar el asiento a cero:
        igtf_residual_balance = -total_balance_prev 
        igtf_residual_amount_currency = -total_amount_currency_prev

        # 6. Agregamos la línea del IGTF usando el Command nativo de Odoo
        vals.append(Command.create({
            'name': 'IGTF',
            'account_id': igtf_account_id,  
            'currency_id': payment.currency_id.id,
            'balance': igtf_residual_balance,                  # Residual exacto en Bs.
            'amount_currency': igtf_residual_amount_currency,   # Residual exacto en Divisa.
            **common_vals
        }))

        return vals
        

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
            
            if is_customer: # use your partner_type logic
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
        initial_residual = self.amount_residual
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
            rec.igtf_top_aply = 0.0
            rec.alter_bi_igtf = 0.0
            rec.foreign_bi_igtf = 0.0
            rec.bi_igtf = 0.0
            
            if abs(rec.amount_residual) > 0 or rec.payment_state in ['paid','in_payment']: 
                rec.igtf_top_aply = abs(rec.amount_total_signed) * (self.company_id.igtf_percentage / 100)
                receivable_payable_lines = rec.line_ids.filtered(lambda line: line.account_id.reconcile)

                final_payment_moves = receivable_payable_lines.reconciled_lines_ids.mapped('move_id')

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
                    if rec.move_type in ['out_invoice', 'out_refund']:
                        target_account = partner_context.property_account_receivable_id
                    else:
                        target_account = partner_context.property_account_payable_id

                    igtf_line = payment_move.line_ids.filtered(lambda line: line.account_id.id in account)
                    partner_line = payment_move.line_ids.filtered(lambda l: l.account_id.id == target_account.id)
                    bank_line = payment_move.line_ids.filtered(lambda line: line.account_id.id not in partner_line.mapped('account_id').ids and line.account_id.id not in igtf_line.mapped('account_id').ids)
                    
                    igtf_amount = 0.0
                    amount_base_payment = 0.0
                    if bank_line and partner_line:

                        factura_line = rec.line_ids.filtered(lambda l: l.account_id.id == target_account.id)

                        partial = self.env['account.partial.reconcile'].search([
                            '|',
                            '&', ('debit_move_id', '=', factura_line.id), ('credit_move_id', '=', partner_line.ids),
                            '&', ('debit_move_id', '=', partner_line.ids), ('credit_move_id', '=', factura_line.id)
                        ])
                        bank_amount = abs(bank_line[0].amount_currency)
                        bank_amount_balance = abs(bank_line[0].balance)
                        if partial:
                            partial_amount = abs(sum(partial.mapped('amount')))
                        
                        if igtf_line and partial:
                        
                            igtf_amount = abs(igtf_line[0].balance)
                            igtf_amount_currency = abs(igtf_line[0].amount_currency)
                            partial_amount = abs(sum(partial.mapped('amount')))
                        
                        if not igtf_line and bank_line and partial:
                            igtf_top += partial_amount
                            
                        
                        if igtf_line and bank_line and partial:

                            if payment_move.origin_payment_id and payment_move.origin_payment_id.reconciled_invoices_count > 1:

                                amount_base_payment = partial_amount

                            elif 'pos_payment_ids' in bank_line[0].move_id._fields:
                                    if bank_line[0].move_id.pos_payment_ids:
                                        amount_base_payment = rec.company_id.currency_id.round(igtf_amount / (rec.company_id.igtf_percentage / 100))

                            elif  rec.company_id.currency_id.round(partial_amount * (rec.company_id.igtf_percentage / 100)) == igtf_amount:
                                    
                                amount_base_payment = partial_amount
                                igtf_amount = amount_base_payment * (rec.company_id.igtf_percentage / 100)
                               
                            else:
                                if rec.company_id.currency_id.round(bank_amount * (rec.company_id.igtf_percentage / 100)) == igtf_amount_currency:
                                    
                                    amount_base_payment = bank_amount_balance
                                    igtf_amount = igtf_amount 
                                else:
                                    amount_base_payment = partial_amount
                                    igtf_amount = igtf_amount 

                        if igtf_line and partial:
                            alter_bi_igtf += igtf_amount

                    conversion_date = False

                    if rec.invoice_date != False and payment_move.date <= rec.invoice_date:
                        conversion_date = rec.invoice_date
                    else:
                        conversion_date = payment_move.date

                    total_bi_igtf += amount_base_payment

                    if total_bi_igtf > abs(rec.amount_total_signed):
                        total_bi_igtf = abs(rec.amount_total_signed)

                    foreign_bi_igtf += rec.company_id.currency_id._convert(
                        amount_base_payment, 
                        rec.currency_id, 
                        rec.company_id, 
                        conversion_date,
                    )

                    if foreign_bi_igtf > abs(rec.amount_total):
                        foreign_bi_igtf = abs(rec.amount_total)


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
        self._check_draftable()
        self.line_ids.analytic_line_ids.with_context(skip_analytic_sync=True).unlink()
        self.mapped('line_ids').remove_move_reconcile()
        return super().button_draft()
