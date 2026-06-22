from odoo import api, models, fields, _, Command
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_is_zero , float_compare, float_repr, SQL , float_round

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

    destination_account_id_domain = fields.Char(
        compute="_compute_destination_account_id_domain"
    )

    invoices_origin_ids = fields.Many2many('account.move', string='Invoices Origin')

    def _get_default_keep_alter(self):
        return self.env.company.revalorize_payments_vef

    keep_alter_value_vef = fields.Boolean('Keep Amount in alter value', default=_get_default_keep_alter)

    
    @api.onchange('currency_id','date')
    def _onchange_keep_alter_value_vef(self):
        for rec in self:
            if rec.currency_id != rec.company_id.currency_id:
                rec.keep_alter_value_vef = False
                
    @api.onchange('journal_id','is_advance_payment')
    def _onchange_journal_id(self):
       for rec in self:
            if rec.partner_id and rec.journal_id and rec.destination_account_id:
               
                if rec.journal_id and rec.journal_id.is_igtf and rec.is_advance_payment:
                    if rec.destination_account_id and not rec.destination_account_id.is_advance_account:
                        raise UserError(
                            _(
                                "The selected journal is configured for IGTF, so the destination account must be is_advance_account"
                            )) 
                if rec.journal_id and rec.journal_id.is_igtf and not rec.is_advance_payment:
                    raise UserError(
                            _(
                                "The selected journal is configured for IGTF, must be is_advance_payment"
                            )) 


    @api.depends(
        "partner_id", "partner_type",  "is_advance_payment"
    )
    def _compute_destination_account_id(self):

        for payment in self:
            if payment.partner_id:
                customer_account = payment.partner_id.default_advance_customer_account_id.id
                supplier_account = payment.partner_id.default_advance_supplier_account_id.id

                if payment.is_advance_payment:
                    if payment.partner_type == "customer" and customer_account:
                        payment.destination_account_id = customer_account 
                        return
                    elif payment.partner_type == "supplier" and supplier_account:
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
        """Prepare default move line values for a payment.

        Override: IGTF lines are NOT generated if the reconciled invoice's
        journal has is_purchase_international = True.
        """
        for rec in self:
            vals = super(AccountPaymentAndIgtf, self)._prepare_move_line_default_vals(
                write_off_line_vals,
                force_balance
            )

            
            if rec.payment_from_wizard:
                if rec.igtf_percentage and rec.igtf_amount > 0.0 :
                    # Check if any of the related invoices belongs to an
                    # international purchase journal — in that case, skip IGTF.
                    move_ids = rec.invoices_origin_ids
                    is_international = any(
                        m.journal_id.is_purchase_international for m in move_ids
                    )
                    if not is_international:
                        rec._create_igtf_moves_in_payments(vals, write_off_line_vals)
                if rec.igtf_amount <= 0.0: #Nativo
                    total_base_residual = abs(sum(rec.invoices_origin_ids.mapped('amount_residual_signed')))
                    if write_off_line_vals:
                        
                        rec._fix_writeoff_balance(vals, write_off_line_vals)
                    else:
                        if abs(total_base_residual) - abs(vals[0]['balance']) <= 0.1:
                            # FIX balances when diference is decimal
                            if rec.partner_type == "customer":
                                vals[0].update({"balance": total_base_residual})
                                vals[1].update({"balance": -total_base_residual})
                            else:
                                vals[0].update({"balance": -total_base_residual})
                                vals[1].update({"balance": total_base_residual})

            return vals
    
    def calculate_igtf_for_payment(self, invoice, amount_payment, payment_currency, payment_date, base=False):
        return self.env["l10n_ve_igtf.utils"].calculate_igtf_for_payment(
            invoice, amount_payment, payment_currency, payment_date,
            company=self.company_id, base=base,
        )

    def convert_to_company_currency(self, from_currency, amount, date=False, invoice_currency=False):
        self.ensure_one()
        return self.env["l10n_ve_igtf.utils"]._convert_to_company_currency(
            from_currency, amount, date, self.company_id, invoice_currency=invoice_currency,
        )

    def convert_to_external_currency(self, from_currency, amount, date=False):
        self.ensure_one()
        return self.env["l10n_ve_igtf.utils"]._convert_to_external_currency(
            from_currency, amount, date, self.company_id,
        )

        
    def _create_igtf_moves_in_payments(self, vals, write_off_line_vals = False):
        
        igtf_account = (
            self.partner_id.default_advance_customer_account_id.id
            if self.partner_type == "customer"
            else  self.partner_id.default_advance_supplier_account_id.id
        )
        if self.env.context.get("from_pos", False):
            return

        for payment in self:
            if payment.igtf_amount > 0.0:
                if payment.payment_type == "inbound":
                    vals_igtf = [x for x in vals if x["account_id"] == igtf_account]
                    if not vals_igtf:
                        payment._prepare_inbound_move_line_igtf_vals(vals, write_off_line_vals)

                if payment.payment_type == "outbound":
                    vals_igtf = [x for x in vals if x["account_id"] == igtf_account]
                    if not vals_igtf:
                        payment._prepare_outbound_move_line_igtf_vals(vals,write_off_line_vals)

    def _fix_writeoff_balance(self, vals, write_off_line_vals):
        """Force counterpart line to match the invoices' actual residual
        in company currency, and adjust the write-off to keep the entry
        balanced. Mirrors the residual-based adjustment in
        _prepare_inbound_move_line_igtf_vals for the non-IGTF case,
        preventing descuadres between individual conversion in the
        wizard and aggregate _convert in the payment lines.
        """
         
        for rec in self:
            if not write_off_line_vals or len(vals) < 3:
                continue
            comp_curr = rec.company_id.currency_id
            currency = rec.currency_id

            # Current counterpart balance and its direction
            cpart = vals[1]
            current = cpart.get('balance', 0) or (cpart.get('debit', 0) - cpart.get('credit', 0))
            is_debit = cpart.get('debit', 0) > 0

            # Actual residual in company currency from the invoices
            invoice_residual = sum(rec.invoices_origin_ids.mapped('amount_residual_signed'))
            residual_abs = abs(invoice_residual) if invoice_residual else 0.0

            # Preserve the sign of the current counterpart line
            expected = residual_abs if is_debit else -residual_abs

            diff = expected - current
            if comp_curr.is_zero(diff):
                return

            # Force counterpart to match the invoice residual
            cpart['balance'] = expected
            if is_debit:
                cpart.update({'debit': expected, 'credit': 0.0})
            else:
                cpart.update({'debit': 0.0, 'credit': expected})
            # Recalculate amount_currency from the forced balance
            # Preserve sign: debit > 0 → amount_currency > 0, credit > 0 → amount_currency < 0
            amt = comp_curr._convert(
                abs(expected), currency, rec.company_id, rec.date,
            )
            cpart['amount_currency'] = -amt if not is_debit else amt

            # Absorb the difference in the write-off line to keep total = 0
            w_off = vals[2]
            w_off['balance'] = w_off.get('balance', 0) - diff
            if w_off['balance'] > 0:
                w_off.update({'debit': w_off['balance'], 'credit': 0.0})
            else:
                w_off.update({'debit': 0.0, 'credit': -w_off['balance']})
            # Recalculate write-off amount_currency with correct sign
            w_is_debit = w_off.get('debit', 0) > 0
            w_amt = comp_curr._convert(
                abs(w_off['balance']), currency, rec.company_id, rec.date,
            )
            w_off['amount_currency'] = -w_amt if not w_is_debit else w_amt

    def _create_inbound_move_line_igtf_vals(self, vals, igtf_base):
        """
        Appends the IGTF (Financial Transaction Tax) move line values to the 
        existing list of line values for inbound payments.

        This method identifies the appropriate IGTF account from the partner's 
        configuration, calculates the tax amount in both transaction and 
        company currency, and appends a new dictionary to 'vals'.

        :param vals: List of dictionaries representing the move lines to be created.
        
        :raises UserError: If the IGTF account is not configured on the Partner's 
                        advance account fields.

        :return: The updated 'vals' list including the new IGTF line dictionary.
        """
        for rec in self:
            currency = rec.currency_id
            
            igtf_account = (
                rec.company_id.customer_account_igtf_id.id
                if rec.partner_type == "customer"
                else rec.company_id.supplier_account_igtf_id.id
            )

            if not igtf_account:
                raise UserError(_('Igtf Account in must be assigned in companies settings'))
            
            igtf_amount_curr = rec.igtf_amount
            
            if float_compare(igtf_amount_curr, 0.0, precision_digits=currency.decimal_places) > 0.0:
               
                if len(vals) == 2: 
                    # Fix when igtf has no writte_off / not cumulated residual account
                    current_net_balance = 0.0
                    for line in vals:
                        line_balance = line.get('balance') or (line.get('debit', 0.0) - line.get('credit', 0.0))
                        current_net_balance += line_balance

                
                    igtf_amount_currency = abs(rec.igtf_amount)
                    
                    cc = rec.company_id.currency_id
                    final_igtf_balance = float(float_repr(current_net_balance, precision_digits=cc.decimal_places))
                    credit = abs(final_igtf_balance) 
                    vals.append({
                        "name": "IGTF",
                        "currency_id": currency.id,
                        "amount_currency": -igtf_amount_currency,
                        "account_id": igtf_account,
                        "partner_id": rec.partner_id.id,
                        "credit": credit,
                        "balance": -credit,
                    })
                
                else: 
                    # Fix when igtf has writte_off / cumulated residual account
                    credit = abs(igtf_base) 
                    vals.append({
                        "name": "IGTF",
                        "currency_id": currency.id,
                        "amount_currency": -igtf_amount_curr,
                        "account_id": igtf_account,
                        "partner_id": rec.partner_id.id,
                        "credit": credit,
                        "balance": -credit,
                    })

        return vals

    def _create_outbound_move_line_igtf_vals(self, vals, igtf_base):
      
        """
        Appends the IGTF (Financial Transaction Tax) move line values to the 
        existing list of line values for inbound payments.

        This method identifies the appropriate IGTF account from the partner's 
        configuration, calculates the tax amount in both transaction and 
        company currency, and appends a new dictionary to 'vals'.

        :param vals: List of dictionaries representing the move lines to be created.
        
        :raises UserError: If the IGTF account is not configured on the Partner's 
                        advance account fields.

        :return: The updated 'vals' list including the new IGTF line dictionary.
        """
        for rec in self:
            currency = rec.currency_id
            
            igtf_account = (
                rec.company_id.customer_account_igtf_id.id
                if rec.partner_type == "customer"
                else rec.company_id.supplier_account_igtf_id.id
            )

            if not igtf_account:
                raise UserError(_('Igtf Account in must be assigned in companies settings'))
            

            igtf_amount_curr = rec.igtf_amount
            
            if float_compare(igtf_amount_curr, 0.0, precision_digits=currency.decimal_places) > 0.0:
               
                if len(vals) == 2: 
                    # Fix when igtf has no writte_off / not cumulated residual account
                    current_net_balance = 0.0
                    for line in vals:
                        line_balance = line.get('balance') or (line.get('debit', 0.0) - line.get('credit', 0.0))
                        current_net_balance += line_balance

                
                    igtf_amount_currency = abs(rec.igtf_amount)
                    
                    cc = rec.company_id.currency_id
                    final_igtf_balance = float(float_repr(current_net_balance, precision_digits=cc.decimal_places))
                    credit = abs(final_igtf_balance) 
                    vals.append({
                        "name": "IGTF",
                        "currency_id": currency.id,
                        "amount_currency": igtf_amount_currency,
                        "account_id": igtf_account,
                        "partner_id": rec.partner_id.id,
                        "credit": credit,
                        "balance": credit,
                    })
                
                else: 
                    # Fix when igtf has writte_off / cumulated residual account
                    credit = abs(igtf_base) 
                    vals.append({
                        "name": "IGTF",
                        "currency_id": currency.id,
                        "amount_currency": igtf_amount_curr,
                        "account_id": igtf_account,
                        "partner_id": rec.partner_id.id,
                        "credit": credit,
                        "balance": credit,
                    })
            

        return vals
  

    def _prepare_inbound_move_line_igtf_vals(self, vals, write_off_line_vals = False):
        """ Adjusts the journal items values (`vals`) to inject the IGTF tax calculation,
        ensuring proper multi-currency balance alignment and checking for total invoice closures.

        This method recalculates the customer receivable line (`vals[1]`) by isolating the
        proportional VEF/USD amount corresponding to the transaction's core payment vs its 
        associated IGTF tax. It also provides a safeguard to force the receivable balance 
        to match the total outstanding invoice residual value when the payment completely 
        extinguishes the debt.

        :param list vals: A list of dictionaries representing the `account.move.line` 
                        values prepared by Odoo's payment creation wizard.
                        - vals[0]: Liquidity/Bank line.
                        - vals[1]: Counterpart/Receivable line.
                        - vals[2]: (Optional) Write-off/Difference line.
        :param list/bool write_off_line_vals: Optional list containing standard write-off 
                                            line structures to absorb differences.

        :return: None. Modifies the mutable `vals` list in-place and triggers the 
                internal tax row generation via `_create_inbound_move_line_igtf_vals`.
        """
        
        for rec in self:
            lines = [line for line in vals]
            if rec.payment_type == "inbound":
                total_base_residual = abs(sum(rec.invoices_origin_ids.mapped('amount_residual_signed')))
                top_igtf = abs(sum(rec.invoices_origin_ids.mapped('igtf_top_aply')))

                top_igtf_residual_base = total_base_residual + top_igtf
                currency = rec.currency_id 
                precision = currency.decimal_places

                credit_line_unrounded = lines[1]["amount_currency"] + rec.igtf_amount
                credit_line = credit_line_unrounded
               
                
                credit_amount = abs(lines[1]["balance"])
                
                amount = credit_amount
                igtf_base = 0.0
                total_base_residual_converted = 0.0
                precision_base = self.env.company.currency_id.decimal_places
                if rec.igtf_amount > 0.0: 
                    balance = abs(lines[0]["balance"])
                    # for exedent payment and multipayment
                    if balance - top_igtf_residual_base >= 1.0 or len(rec.invoices_origin_ids) > 1: 
                        igtf_base = top_igtf
                        amount = credit_amount - igtf_base
                    else:

                        porcion_igtf = rec.igtf_amount / abs(lines[0]["amount_currency"])
                        igtf_base = float_round((balance * porcion_igtf), precision_digits=precision_base)
                        
                        #Prevent apply more IGTF than
                        if top_igtf - igtf_base  <= 0.1: 
                            igtf_base = float_round(top_igtf,precision_digits=precision_base)

                        amount = credit_amount - igtf_base
                        
                    total_base_residual_converted =  rec.company_id.currency_id._convert( 
                        total_base_residual, 
                        currency, 
                        rec.company_id, 
                        rec.date,
                    )
                        

                    total_base_residual_converted_with_igtf = float_round(abs(total_base_residual_converted) + abs(rec.igtf_amount), precision_digits=precision)
                    if total_base_residual_converted_with_igtf == abs(lines[0]["amount_currency"]): 
                        #Ajust cxc balance
                        if abs(credit_amount) > abs(total_base_residual):
                            amount = abs(total_base_residual)


                if float_compare(rec.igtf_amount, 0.0, precision_digits=precision) > 0.0:
                    if not write_off_line_vals:
                        
                        vals[1].update({"amount_currency": credit_line, "balance": -amount})
                    else:
                        
                        vals[1].update({"balance": -total_base_residual})
                
                if write_off_line_vals:
                    # Recalculate write-off balance to compensate the adjusted counterpart
                    cc = rec.company_id.currency_id
                    net_no_writeoff = sum(
                        v.get('balance', 0) or (v.get('debit', 0.0) - v.get('credit', 0.0))
                        for v in vals
                        if v is not vals[2]
                    ) - igtf_base
                    vals[2]['balance'] = -net_no_writeoff
                    if vals[2]['balance'] != 0:
                        vals[2]['amount_currency'] = cc._convert(
                            vals[2]['balance'], currency, rec.company_id, rec.date,
                        )
                    else:
                        vals[2]['amount_currency'] = 0.0
                
                rec._create_inbound_move_line_igtf_vals(vals,igtf_base)
                
    def _prepare_outbound_move_line_igtf_vals(self, vals,write_off_line_vals =False):
        """ Adjusts the journal items values (`vals`) to inject the IGTF tax calculation,
        ensuring proper multi-currency balance alignment and checking for total invoice closures.

        This method recalculates the provider receivable line (`vals[1]`) by isolating the
        proportional VEF/USD amount corresponding to the transaction's core payment vs its 
        associated IGTF tax. It also provides a safeguard to force the receivable balance 
        to match the total outstanding invoice residual value when the payment completely 
        extinguishes the debt.

        :param list vals: A list of dictionaries representing the `account.move.line` 
                        values prepared by Odoo's payment creation wizard.
                        - vals[0]: Liquidity/Bank line.
                        - vals[1]: Counterpart/Receivable line.
                        - vals[2]: (Optional) Write-off/Difference line.
        :param list/bool write_off_line_vals: Optional list containing standard write-off 
                                            line structures to absorb differences.

        :return: None. Modifies the mutable `vals` list in-place and triggers the 
                internal tax row generation via `_create_inbound_move_line_igtf_vals`.
        """

        for rec in self:
            lines = [line for line in vals]
            if rec.payment_type == "outbound":

                total_base_residual = abs(sum(rec.invoices_origin_ids.mapped('amount_residual_signed')))
                top_igtf = abs(sum(rec.invoices_origin_ids.mapped('igtf_top_aply')))

                top_igtf_residual_base = total_base_residual + top_igtf
                currency = rec.currency_id 
                precision = currency.decimal_places

                debit_line_unrounded = lines[1]["amount_currency"] - rec.igtf_amount
                debit_line = debit_line_unrounded
               
                
                debit_amount = abs(lines[1]["balance"])
                
                amount = debit_amount
                igtf_base = 0.0
                total_base_residual_converted = 0.0
                precision_base = self.env.company.currency_id.decimal_places

                if rec.igtf_amount > 0.0: 

                    balance = abs(lines[0]["balance"])
                    # for exedent payment and multipayment
                    if balance - top_igtf_residual_base >= 1.0 or len(rec.invoices_origin_ids) > 1: 
                        igtf_base = top_igtf
                        amount = debit_amount - igtf_base
                    else:

                        porcion_igtf = rec.igtf_amount / abs(lines[0]["amount_currency"])
                        igtf_base = float_round((balance * porcion_igtf), precision_digits=precision_base)
                        
                        #Prevent apply more IGTF than
                        if top_igtf - igtf_base  <= 0.1: 
                            igtf_base = float_round(top_igtf,precision_digits=precision_base)

                        amount = debit_amount - igtf_base
                        
                    total_base_residual_converted =  rec.company_id.currency_id._convert( 
                        total_base_residual, 
                        currency, 
                        rec.company_id, 
                        rec.date,
                    )
                        

                    total_base_residual_converted_with_igtf = float_round(abs(total_base_residual_converted) + abs(rec.igtf_amount), precision_digits=precision)
                    if total_base_residual_converted_with_igtf == abs(lines[0]["amount_currency"]): 
                        # Ajust cxp balance
                        if abs(debit_amount) > abs(total_base_residual):
                            amount = abs(total_base_residual)
                
                if float_compare(rec.igtf_amount, 0.0, precision_digits=precision) > 0.0:
                    if not write_off_line_vals:
                        
                        vals[1].update({"amount_currency": debit_line, "balance": amount})
                    else:
                        
                        vals[1].update({"balance": total_base_residual})
                
                if write_off_line_vals:
                    # Recalculate write-off balance to compensate the adjusted counterpart
                    cc = rec.company_id.currency_id
                    net_no_writeoff = sum(
                        v.get('balance', 0) or (v.get('debit', 0.0) - v.get('credit', 0.0))
                        for v in vals
                        if v is not vals[2]
                    ) + igtf_base
                    vals[2]['balance'] = net_no_writeoff
                    if vals[2]['balance'] != 0:
                        vals[2]['amount_currency'] = cc._convert(
                            vals[2]['balance'], currency, rec.company_id, rec.date,
                        )
                    else:
                        vals[2]['amount_currency'] = 0.0

                rec._create_outbound_move_line_igtf_vals(vals, igtf_base)

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
    
    #Override
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

    @api.depends('is_advance_payment')
    def _compute_destination_account_id_domain(self):
        """
        Computes a dynamic domain for the destination_account_id field based on 
        whether the payment is marked as an advance.

        Logic:
        - If is_advance_payment is True:
            * For Suppliers: Filters for 'Current Asset' accounts marked as advance 
            accounts (Prepayments to vendors).
            * For Customers: Filters for 'Current Liability' accounts marked as advance 
            accounts (Payments received in advance).
        - If is_advance_payment is False:
            * Standard behavior: Filters for 'Receivable' and 'Payable' accounts, 
            excluding those specifically flagged for advances.

        :return: Sets the string representation of the domain in destination_account_id_domain.
        """
        for rec in self:
            domain = False 
            company_domain = [('company_ids', 'in', [rec.company_id.id]), ('reconcile', '=', True)]
            if rec.is_advance_payment:
                if rec.partner_type == 'supplier':
                   domain = company_domain + [
                        ('account_type', '=', 'asset_current'),
                        ('is_advance_account', '=', True)
                    ]
                else:
                    domain = company_domain + [
                        ('account_type', '=', 'liability_current'),
                        ('is_advance_account', '=', True)
                    ]
            else:
                if rec.partner_type == 'supplier':
                    domain = company_domain + [
                        ('account_type', '=', 'asset_receivable'),
                        ('is_advance_account', '=', False)
                    ]
                else:
                    domain = company_domain + [
                        ('account_type', '=', 'liability_payable'),
                        ('is_advance_account', '=', False)
                    ]
            
            rec.destination_account_id_domain = str(domain)

    
    @api.constrains('is_advance_payment', 'destination_account_id', 'partner_type')
    def _check_advance_payment_account(self):
        """
        Validates the destination account based on the payment type (Standard vs. Advance).

        Constraints:
        - Bypasses validation during module installation/update or if 'skip_check' is in context.
        - If 'is_advance_payment' is True:
            * Suppliers: Account must be 'Current Asset' and flagged as 'is_advance_account'.
            * Customers: Account must be 'Current Liability' and flagged as 'is_advance_account'.
        - If 'is_advance_payment' is False:
            * Prevents the use of accounts flagged as 'is_advance_account'.
            * Ensures standard payments use only 'Receivable' or 'Payable' account types.

        :raises ValidationError: If the selected account does not match the required 
                                type or advance flag for the current partner type.
        """
        
        for rec in self:
            if self.env.context.get('install_mode') or self.env.context.get('skip_check'):
                return
    
            if not rec.destination_account_id:
                continue

            acc = rec.destination_account_id

            if rec.is_advance_payment:
                if rec.partner_type == 'supplier':
                    if acc.account_type != 'asset_current' or not acc.is_advance_account:
                        raise UserError(_(
                            "For vendor advances, the account must be 'Current Assets' and flagged as an 'Advance Account'."
                        ))
                elif rec.partner_type == 'customer':
                    if acc.account_type != 'liability_current' or not acc.is_advance_account:
                        raise UserError(_(
                            "For customer advances, the account must be 'Current Liabilities' and flagged as an 'Advance Account'."
                        ))
            else:
                if acc.is_advance_account:
                    raise UserError(_(
                        "You cannot use an 'Advance Account' for a standard payment. Please uncheck 'Is Advance Payment' or change the account."
                    ))
                
                if acc.account_type not in ('asset_receivable', 'liability_payable'):
                    raise UserError(_(
                        "Standard payments must use 'Receivable' or 'Payable' account types."
                    ))