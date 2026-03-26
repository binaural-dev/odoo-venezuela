from odoo import api, models, fields, _ ,Command
from odoo.exceptions import UserError
import logging
from odoo.tools.float_utils import float_round 
from odoo.tools import float_is_zero , float_compare

_logger = logging.getLogger(__name__)


class AccountPaymentRegisterIgtf(models.TransientModel):
    _inherit = "account.payment.register"

    is_igtf = fields.Boolean(string="IGTF", 
                             help="IGTF")
                             
    amount_with_igtf = fields.Float(
        string="Amount with IGTF", 
    )

    def _default_igtf_percent_from_company(self):
        return self.env.company.igtf_percentage

    igtf_percentage = fields.Float(
        string="IGTF Percentage Aplicado",
        default=_default_igtf_percent_from_company,
        help="IGTF aplicado, obtenido de la configuración de la compañía en el momento de la creación.",
        store=True,
    )

    igtf_amount = fields.Float(
        string="IGTF Amount", 
        help="IGTF Amount"
    )

    is_igtf_on_foreign_exchange = fields.Boolean(
        string="IGTF on Foreign Exchange?",
        default=False,
        help="IGTF on Foreign Exchange?",
        store=True,
    )

    amount_without_difference = fields.Monetary(
        string="Amount without Difference",
    )

    payment_difference = fields.Monetary(
        compute='_compute_payment_difference',readonly=False)


    igtf_to_show = fields.Monetary(string="Amount with IGTF")

    available_journal_ids = fields.Many2many(
        comodel_name='account.journal',
        compute='_compute_available_journal_ids'
    )

    show_payment_difference = fields.Boolean(compute='_compute_show_payment_difference', readonly=False)

    last_computed_amount = fields.Float("Last Computed Amount", digits=(16, 2))

    @api.depends('can_edit_wizard', 'source_amount', 'source_amount_currency', 'source_currency_id', 'company_id', 'currency_id', 'payment_date')
    def _compute_amount(self):
        
        for wizard in self:
            batch_result = wizard.batches
            base_amount = 0.0
            if not wizard.journal_id or not wizard.currency_id or not wizard.payment_date :
                base_amount = wizard._get_total_amounts_to_pay(wizard.batches)['amount_by_default'] or 0.0
            elif wizard.source_currency_id and wizard.can_edit_wizard:
                
                if isinstance(batch_result, dict) and 'lines' in batch_result:
                    amounts = wizard._get_total_amounts_to_pay(batch_result)
                    base_amount = amounts[0] if amounts else 0.0
                else:
                    base_amount = wizard._get_total_amounts_to_pay(wizard.batches)['amount_by_default']
            else:
                base_amount = 0.0 

            final_amount = base_amount
            total_igtf_amount = 0.0
            if wizard.is_igtf:

                move_ids = wizard.get_moves()

                for invoice in move_ids:
                    igtf_for_invoice = wizard.calculate_igtf_for_payment(
                        invoice, 
                        base_amount, 
                        self.currency_id
                    )
                    total_igtf_amount += abs(igtf_for_invoice)
                final_amount = base_amount + total_igtf_amount
            
            wizard.amount = final_amount
            wizard.igtf_amount = total_igtf_amount
            wizard.igtf_to_show = total_igtf_amount
            wizard.last_computed_amount = final_amount   

    def get_moves(self):
        """ Return the moves to pay from the context.
        Overridden to ensure that we always get the moves from the context,
        even if we are in edit mode.
        """
        ids=self.env.context.get("active_id") or self.env.context.get("active_ids")

        if isinstance(ids, int):
            return self.env["account.move"].browse([ids])
        else:
            move_lines = self.env["account.move.line"].browse(ids)
            return set(move_lines.mapped("move_id"))

    @api.onchange('payment_difference')
    def _onchange_diference(self):
        for wizard in self:
           
            if wizard.can_edit_wizard and wizard.payment_date and wizard.is_igtf:
                currency = wizard.currency_id 
                precision = currency.rounding
                batch_result = wizard.batches
        
                expected_amount = 0.0
                if isinstance(batch_result, dict) and 'lines' in batch_result:
                    amounts = wizard._get_total_amounts_to_pay(batch_result)
                    total_residual = amounts[0] if amounts else 0.0
                    expected_amount = abs(total_residual)

                else:
                    total_residual =  wizard._get_total_amounts_to_pay(batch_result)['amount_by_default']

                    expected_amount = abs(total_residual)

                
                if wizard.is_igtf and float_compare(wizard.igtf_to_show, 0.0, precision_rounding=precision) > 0.0:
                    
                    expected_amount += wizard.igtf_to_show
                raw_difference = expected_amount - abs(wizard.amount)
                
               
                rounded_difference = raw_difference
                
                
                if abs(rounded_difference) < wizard.currency_id.rounding:
                    wizard.payment_difference = 0.0
                    wizard.show_payment_difference = False
                else:
                    
                    wizard.payment_difference = rounded_difference
                    wizard.show_payment_difference = True


    @api.onchange("igtf_to_show")
    def _compute_amount_without_difference(self):
        for rec in self:
            
            amount_without_difference = 0.0
            move_ids=self.get_moves()
            if len(move_ids) == 1:
                for move_id in move_ids:
                    source_amount = self.source_amount
                    due_currency_id = self.source_currency_id
                    residual = due_currency_id._convert(source_amount,self.currency_id,company=move_id.company_id,date=self.payment_date) 
                    
                    if rec.amount <= residual + residual * (rec.igtf_percentage / 100):
                        amount_without_difference = amount_without_difference + (rec.amount - rec.igtf_to_show)
                    
                    elif rec.amount > residual + residual * (rec.igtf_percentage / 100) :
                        amount_without_difference = amount_without_difference + residual  
            else:
                source_amount = self.source_amount
                due_currency_id = self.source_currency_id
                residual = due_currency_id._convert(source_amount,self.currency_id,company=self.company_id,date=self.payment_date) 
                
                if rec.amount <= residual + residual * (rec.igtf_percentage / 100):
                    amount_without_difference = amount_without_difference + (rec.amount - rec.igtf_to_show)
                
                elif rec.amount > residual + residual * (rec.igtf_percentage / 100) :
                    amount_without_difference = amount_without_difference + residual  

            rec.amount_without_difference = amount_without_difference

                             
    @api.onchange("journal_id","currency_id")
    def _compute_check_igtf(self):
        """ Check if the company is a ordinary contributor.

        Exception: if the invoice's journal has is_purchase_international=True,
        IGTF is not applicable regardless of the payment journal's is_igtf flag.
        """
        for payment in self:
            payment.is_igtf = False
            if payment.journal_id.is_igtf:

                move_ids = self.get_moves()
                for move_id in move_ids:
                    # Skip IGTF for invoices belonging to international purchase journals
                    if move_id.journal_id.is_purchase_international:
                        continue
                    if (
                        payment.partner_id._check_igtf_apply_improved(move_id.move_type)
                        and payment.currency_id != self.env.ref("base.VEF")
                    ):
                        payment.is_igtf = True
            
    @api.onchange("is_igtf", "igtf_to_show")
    def _compute_amount_with_igtf(self):
        """Compute the amount with igtf of the payment"""
        for payment in self:
            if payment.is_igtf:
                payment.amount_with_igtf = payment.amount + payment.igtf_to_show

    @api.onchange("amount","payment_date")
    def _onchange_amount(self):
        for payment in self:
            
            
            diff = payment.amount - payment.last_computed_amount
            if float_is_zero(diff, precision_rounding=payment.currency_id.rounding):
                return
            move_ids=self.get_moves()

            amount = False
            for rec in move_ids:
                if payment.is_igtf:
                    invoice = rec
                   
                    amount = amount + payment.calculate_igtf_for_payment(invoice, payment.amount,payment.currency_id)
            if payment.is_igtf:
                payment.igtf_to_show = abs(amount)
                payment.igtf_amount = abs(amount)
                
            else:
                payment.igtf_to_show = 0.0
                payment.igtf_amount = 0.0

            
            payment.last_computed_amount = payment.amount

    def calculate_igtf_for_payment(self, invoice, amount_payment, payment_currency, base = False):
        
        currency = invoice.currency_id
        precision = currency.rounding
        
        due_currency_id = invoice.currency_id
        due_amount = self.convert_to_company_currency(due_currency_id, invoice.amount_residual,self.payment_date) #deuda en moneda de la compañia

        
        payment_amount = self.convert_to_company_currency(payment_currency, amount_payment,self.payment_date) 
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
            return self.convert_to_external_currency(payment_currency, igtf, self.payment_date)
        else:
            return igtf
    
    def convert_to_company_currency(self, from_currency,amount,date):
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
            date,

        )
        
        return converted_amount
    
    def convert_to_external_currency(self, from_currency,amount,date):
        """
        Convierte un monto desde una moneda específica a la moneda base de la compañía.
        """
        self.ensure_one()
        company_currency = self.company_id.currency_id
   
        converted_amount = company_currency._convert(
            amount, 
            from_currency, 
            self.company_id, 
            date,
        )
        
        return converted_amount
        
    @api.onchange('journal_id')
    def _compute_is_igtf_journal(self):
        for record in self:
            if record.journal_id.currency_id and record.journal_id.currency_id != self.env.ref("base.VEF"):
                record.is_igtf_on_foreign_exchange = True
            else:
                record.is_igtf_on_foreign_exchange = False
    
    @api.depends('available_journal_ids')
    def _compute_journal_id(self):
        for wizard in self:
            if wizard.can_edit_wizard:
                batch = wizard.batches[0]
                wizard.journal_id = wizard._get_batch_journal(batch)
            else:
                wizard.journal_id = self.env['account.journal'].search([
                    *self.env['account.journal']._check_company_domain(wizard.company_id),
                    ('type', 'in', ('bank', 'cash')),('is_igtf', '!=', True),
                    ('id', 'in', self.available_journal_ids.ids),
                ], limit=1)

    @api.model
    def _get_batch_journal(self, batch_result):
        
        payment_values = batch_result['payment_values']
        foreign_currency_id = payment_values['currency_id']
        partner_bank_id = payment_values['partner_bank_id']
        company = min(batch_result['lines'].company_id, key=lambda c: len(c.parent_ids))

        currency_domain = [('currency_id', '=', foreign_currency_id)]
        partner_bank_domain = [('bank_account_id', '=', partner_bank_id)]

        default_domain = [
            *self.env['account.journal']._check_company_domain(company),
            ('type', 'in', ('bank', 'cash', 'credit')),
            ('is_igtf', '!=', True),
            ('id', 'in', self.available_journal_ids.ids)
        ]

        if partner_bank_id:
            extra_domains = (
                currency_domain + partner_bank_domain,
                partner_bank_domain,
                currency_domain,
                [],
            )
        else:
            extra_domains = (
                currency_domain,
                [],
            )

        for extra_domain in extra_domains:
            journal = self.env['account.journal'].search(default_domain + extra_domain, limit=1)
            if journal:
                return journal

        return self.env['account.journal']
            
    @api.model
    def _get_wizard_values_from_batch(self, batch_result, create=False): #obtiene los valores al abrir wizard de pago
        wizard_values = super()._get_wizard_values_from_batch(batch_result)

        batch_lines = batch_result['lines']
        # Extraemos los IDs de las facturas (move_id) vinculadas a esas líneas
        invoice_ids = batch_lines.mapped('move_id')

        source_amount = wizard_values['source_amount_currency'] 
        source = wizard_values['source_amount']

        wizard_values['igtf_amount'] = 0.0
        wizard_values['igtf_percentage'] = self.igtf_percentage
        wizard_values['is_igtf_on_foreign_exchange'] = self.is_igtf_on_foreign_exchange
        
        igtf = 0.0
        final_amount_with_igtf = 0.0
        total_igtf_amount = 0.0
        if create and create.is_igtf:
            
            igtf_for_invoice = self.calculate_igtf_for_payment(
                invoice_ids, 
                invoice_ids.amount_residual,
                self.currency_id 
            )
            total_igtf_amount += igtf_for_invoice
            base_abs = abs(source_amount)
            final_amount_with_igtf = base_abs + total_igtf_amount
            igtf = self.convert_to_company_currency(invoice_ids.currency_id, total_igtf_amount, self.payment_date)

            wizard_values['source_amount'] = source  + igtf 
            wizard_values['source_amount_currency'] =  final_amount_with_igtf 
            wizard_values['igtf_amount'] = total_igtf_amount
            wizard_values['igtf_percentage'] = self.igtf_percentage
            wizard_values['is_igtf_on_foreign_exchange'] = self.is_igtf_on_foreign_exchange
        
        return wizard_values
    
    def _create_payment_vals_from_wizard(self, batch_result):
        """
        This method is used to add the foreign rate and the foreign inverse rate to the payment
        values that are used to create the payment from the wizard.
        """
        batch_lines = batch_result['lines']
        # Extraemos los IDs de las facturas (move_id) vinculadas a esas líneas
        invoice_ids = batch_lines.mapped('move_id')

        payment_vals = super()._create_payment_vals_from_wizard(batch_result)
        payment_vals.update(
            {
                "igtf_amount": self.igtf_amount if self.igtf_amount != 0.0 else self.igtf_to_show,
                "payment_from_wizard": True,
                "igtf_percentage": self.igtf_percentage,
                "is_igtf_on_foreign_exchange": self.is_igtf_on_foreign_exchange,
                "invoices_origin_ids": invoice_ids,
                "currency_id": self.currency_id.id,
            }
        )

        return payment_vals
   
    def _create_payment_vals_from_batch(self, batch_result): #crea los valores para cada pago individual

        batch_lines = batch_result['lines']
        # Extraemos los IDs de las facturas (move_id) vinculadas a esas líneas
        invoice_ids = batch_lines.mapped('move_id')
        batch_values = self._get_wizard_values_from_batch(batch_result, create=self)

        if batch_values['payment_type'] == 'inbound':
            partner_bank_id = self.journal_id.bank_account_id.id
        else:
            partner_bank_id = batch_result['payment_values']['partner_bank_id']

        payment_method_line = self.payment_method_line_id

        if batch_values['payment_type'] != payment_method_line.payment_type:
            payment_method_line = self.journal_id._get_available_payment_method_lines(batch_values['payment_type'])[:1]

        payment_vals = {
            'date': self.payment_date,
            'amount': batch_values['source_amount_currency'],
            'payment_type': batch_values['payment_type'],
            'partner_type': batch_values['partner_type'],
            'memo': self._get_communication(batch_result['lines']),
            'journal_id': self.journal_id.id,
            'company_id': self.company_id.id,
            'currency_id': self.currency_id.id,
            'partner_id': batch_values['partner_id'],
            'igtf_amount': batch_values['igtf_amount'],
            'payment_from_wizard': True,
            'igtf_percentage': batch_values['igtf_percentage'],
            'is_igtf_on_foreign_exchange': batch_values['is_igtf_on_foreign_exchange'],
            'payment_method_line_id': payment_method_line.id,
            'destination_account_id': batch_result['lines'][0].account_id.id,
            'write_off_line_vals': [],
            'invoices_origin_ids': invoice_ids,
        }

        if partner_bank_id:
            payment_vals['partner_bank_id'] = partner_bank_id

        total_amount_values = self._get_total_amounts_to_pay([batch_result])
        total_amount = total_amount_values['amount_by_default']
        currency = self.env['res.currency'].browse(batch_values['source_currency_id'])
        if total_amount_values['epd_applied']:
            payment_vals['amount'] = total_amount

            epd_aml_values_list = []
            for aml in batch_result['lines']:
                if aml.move_id._is_eligible_for_early_payment_discount(currency, self.payment_date):
                    epd_aml_values_list.append({
                        'aml': aml,
                        'amount_currency': -aml.amount_residual_currency,
                        'balance': currency._convert(-aml.amount_residual_currency, aml.company_currency_id, self.company_id, self.payment_date),
                    })

            open_amount_currency = (batch_values['source_amount_currency'] - total_amount) * (-1 if batch_values['payment_type'] == 'outbound' else 1)
            open_balance = currency._convert(open_amount_currency, aml.company_currency_id, self.company_id, self.payment_date)
            early_payment_values = self.env['account.move']\
                ._get_invoice_counterpart_amls_for_early_payment_discount(epd_aml_values_list, open_balance)
            for aml_values_list in early_payment_values.values():
                payment_vals['write_off_line_vals'] += aml_values_list
        return payment_vals


    def _create_payments(self):
        """
        This method is called when the wizard is submitted. It will create a move to reconcile with the payment difference

        Returns:
            list: account.payment
        """
        
        payments = super()._create_payments()
        
        ignore_gtf = self.env.context.get("ignore_igtf", False)

        
        is_provider =  self.partner_type == 'supplier'

        due_currency_id = self.source_currency_id
        
        due_amount = due_currency_id._convert(self.source_amount_currency,self.currency_id,company=self.company_id,date=self.payment_date)
       
        for payment in payments:
            
            if payment.igtf_amount:

                amount = payment.amount
            
                if not ignore_gtf:
                    
                    due_amount += payment.igtf_amount 


                self.group_payment = False
                
                if (
                    float_compare(amount, due_amount, precision_rounding=self.currency_id.rounding) == 1
                    and payment.igtf_amount 
                    and self.payment_difference_handling != 'reconcile' 
                    and not self.group_payment
                ):
                    difference = amount - due_amount
                    
                    move_to_reconcile_with_payment_difference = (
                        self._create_move_to_reconcile_with_payment_difference(payment,difference,due_currency_id)
                    )
                    if move_to_reconcile_with_payment_difference:
                        move_to_reconcile_with_payment_difference.action_post()
                    
                        if is_provider:
                            self._reconcile_payment_provider_and_move_lines(
                                payment, move_to_reconcile_with_payment_difference
                            )
                        else:
                            self._reconcile_payment_and_move_lines(
                                payment, move_to_reconcile_with_payment_difference
                            )
                        payment.write({"advanced_move_ids": [(4, move_to_reconcile_with_payment_difference.id)]})
        return payments

    def _create_move_to_reconcile_with_payment_difference(self, payment, diff,due_currency_id):
        """
        Create a move to reconcile with the payment difference

        Args:
            payment (account.payment): Payment object

        Returns:
            account.move: Move object
        """
        advance_account_id = (
            payment.partner_id.default_advance_customer_account_id.id
            if payment.partner_type == "customer"
            else payment.partner_id.default_advance_supplier_account_id.id
        )

        partner_account_id = (
            payment.partner_id.property_account_receivable_id.id
            if payment.partner_type == "customer"
            else payment.partner_id.property_account_payable_id.id
        )

        amount_currency = diff
        currency = payment.currency_id
       

        
        if abs(amount_currency) != 0.0:
            payment_line_ids = [
                Command.create(
                    {
                        "account_id": advance_account_id,
                        "amount_currency": -amount_currency,
                        "payment_id_advance": payment.id,
                        "currency_id":currency.id
                    },
                ),
                Command.create(
                    {
                        "account_id": partner_account_id,
                        "amount_currency": amount_currency,
                        "payment_id_advance": payment.id,
                        "currency_id":currency.id
                    },
                ),
            ]
                
            move_to_reconcile_with_payment_difference = self.env["account.move"].create(
                {
                    "journal_id": self.env.company.advance_payment_igtf_journal_id.id,
                    "date": payment.date,
                    "partner_id": payment.partner_id.id,
                    "vat": payment.partner_id.vat,
                    "ref": "RESTANTE DE PAGO EN DIVISA" + "(" + payment.name + ")",
                    "is_advance_move": True,
                    "line_ids": payment_line_ids,
                    "origin_payment_advanced_payment_id": payment.id
                }
            )

          
            return move_to_reconcile_with_payment_difference
        

    def _reconcile_payment_and_move_lines(self, payment, move):
        """
        Reconcile payment and move lines

        Args:
            payment (account.payment): Payment object
            move (account.move): Move object
        """
        asset_receivable_lines = move.line_ids.filtered(
            lambda x: x.account_id.account_type == "asset_receivable" and not x.reconciled and x.account_id.is_advance_account == True 
        )
        payment_line = payment.move_id.line_ids.filtered(
            lambda x: x.account_id.account_type == "asset_receivable" and not x.reconciled and x.account_id.is_advance_account == True 
        )
        if asset_receivable_lines and payment_line:
            payment_line_to_reconcile = self.env["account.move.line"].browse([payment_line.id])
            payment_line_to_reconcile |= asset_receivable_lines
            payment_line_to_reconcile.reconcile()

    
    def _reconcile_payment_provider_and_move_lines(self, payment, move):
        """
        Reconcile payment and move lines from provider.

        Args:
            payment (account.payment): Payment object
            move (account.move): Move object
        """
        liability_payable_lines = move.line_ids.filtered(
            lambda x: x.account_id.account_type == "liability_payable" and not x.reconciled and x.account_id.is_advance_account == True 
        )
        payment_line = payment.move_id.line_ids.filtered(
            lambda x: x.account_id.account_type == "liability_payable" and not x.reconciled and x.account_id.is_advance_account == True 
        )
        if liability_payable_lines and payment_line:
            payment_line_to_reconcile = self.env["account.move.line"].browse([payment_line.id])
            payment_line_to_reconcile |= liability_payable_lines
            payment_line_to_reconcile.reconcile()


    