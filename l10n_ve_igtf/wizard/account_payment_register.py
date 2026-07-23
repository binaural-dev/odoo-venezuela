from odoo import api, models, fields, _ ,Command
from odoo.exceptions import UserError
import logging
from odoo.tools.float_utils import float_round 
from odoo.tools import float_is_zero , float_compare
from odoo.tools.misc import clean_context
import markupsafe

_logger = logging.getLogger(__name__)


class AccountPaymentRegisterIgtf(models.TransientModel):
    _inherit = "account.payment.register"

    amount = fields.Monetary(currency_field='currency_id', store=True, readonly=False,
        compute='_compute_amount')
    
    is_igtf = fields.Boolean(string="IGTF", 
                             help="IGTF",
                             compute="_compute_check_igtf", store=True)
                             
    amount_with_igtf = fields.Float(
        string="Amount with IGTF",
        
    )

    amount_without_difference = fields.Monetary(
        string="Amount without Difference",
        compute="_compute_amount", readonly=False 
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
        help="IGTF Amount",
        compute="_compute_amount", readonly=False
        
    )
    igtf_to_show = fields.Monetary(string="Amount with IGTF",compute="_compute_amount", readonly=False)

    is_igtf_on_foreign_exchange = fields.Boolean(
        string="IGTF on Foreign Exchange?",
        default=False,
        help="IGTF on Foreign Exchange?",
        store=True,
    )

    

    payment_difference = fields.Monetary(
        compute='_compute_payment_difference',readonly=False)


    

    available_journal_ids = fields.Many2many(
        comodel_name='account.journal',
        compute='_compute_available_journal_ids'
    )

    show_payment_difference = fields.Boolean(compute='_compute_show_payment_difference', readonly=False)

    last_computed_amount = fields.Float("Last Computed Amount", digits=(16, 2))

    def get_moves(self):
        return self.env["l10n_ve_igtf.utils"].get_moves_from_context()
    
    @api.depends('can_edit_wizard', 'source_amount', 'source_amount_currency', 'source_currency_id',
                 'company_id', 'currency_id', 'payment_date', 'installments_mode', 'is_igtf',
                 'custom_user_amount')
    def _compute_amount(self):
        igtf_wizards = self.filtered(lambda w: w.is_igtf)
        other_wizards = self - igtf_wizards

        if other_wizards:
            return super(AccountPaymentRegisterIgtf, other_wizards)._compute_amount()

        for wizard in igtf_wizards:
            if not wizard.journal_id or not wizard.currency_id or not wizard.payment_date or not wizard.is_igtf:
                wizard.amount = wizard.amount or 0.0
                wizard.igtf_to_show = 0.0
                wizard.igtf_amount = 0.0
                wizard.amount_without_difference = 0.0

            elif wizard.custom_user_amount:
                move_ids = self.get_moves()
                igtf = 0.0
                for rec in move_ids:
                    igtf += self.calculate_igtf_for_payment(
                        rec, wizard.amount, wizard.currency_id, wizard.payment_date,
                    )
                wizard.igtf_to_show = abs(igtf)
                wizard.igtf_amount = abs(igtf)
                wizard.amount_without_difference = wizard.amount - abs(igtf)

            else:
                total_amount_values = wizard._get_total_amounts_to_pay(wizard.batches)
                move_ids = self.get_moves()
                igtf = 0.0
                for rec in move_ids:
                    igtf += self.calculate_igtf_for_payment(
                        rec, total_amount_values['amount_by_default'], wizard.currency_id, wizard.payment_date,
                    )
                wizard.amount_without_difference = total_amount_values['amount_by_default']
                wizard.igtf_to_show = abs(igtf)
                wizard.igtf_amount = abs(igtf)
                wizard.amount = total_amount_values['amount_by_default'] + abs(igtf)

            wizard.last_computed_amount = wizard.amount

    
    @api.depends('can_edit_wizard', 'amount', 'installments_mode', 'is_igtf','amount_without_difference')
    def _compute_payment_difference(self):
        igtf_wizards = self.filtered(lambda w: w.is_igtf)
        other_wizards = self - igtf_wizards

        if other_wizards:
            super(AccountPaymentRegisterIgtf, other_wizards)._compute_payment_difference()

        for wizard in igtf_wizards:
            if wizard.payment_date:
                total_amount_values = wizard._get_total_amounts_to_pay(wizard.batches)
                igtf = 0.0
                move_ids = self.get_moves()
                for rec in move_ids:
                    igtf += self.calculate_igtf_for_payment(
                        rec, wizard.amount, wizard.currency_id, wizard.payment_date,
                    )
                efective_amount = abs(wizard.amount) - abs(wizard.igtf_amount)
                if wizard.installments_mode in ('overdue', 'next', 'before_date'):
                    wizard.payment_difference = total_amount_values['amount_for_difference'] - efective_amount
                elif wizard.installments_mode == 'full':
                    wizard.payment_difference = total_amount_values['full_amount_for_difference'] - efective_amount
                else:
                    wizard.payment_difference = total_amount_values['amount_for_difference'] - efective_amount
            else:
                wizard.payment_difference = 0.0
    
   
                             
    @api.depends("journal_id","currency_id")
    def _compute_check_igtf(self):
        """ Check if the company is a ordinary contributor.

        Exception: if the invoice's journal has is_purchase_international=True,
        IGTF is not applicable regardless of the payment journal's is_igtf flag.
        """
        for payment in self:
            payment.is_igtf = False
            payment.is_igtf_on_foreign_exchange = False
            if payment.journal_id.is_igtf:

                move_ids = self.get_moves()
                for move_id in move_ids:
                    # Skip IGTF for invoices belonging to international purchase journals
                    if move_id.journal_id.is_purchase_international:
                        continue
                    if (
                        payment.partner_id._check_igtf_apply_improved(move_id.move_type)
                        and payment.currency_id != self.env.ref("base.VEF") and not move_id.debit_origin_id
                    ):
                        payment.is_igtf = True
                        payment.is_igtf_on_foreign_exchange = True
            

    @api.onchange("amount", "payment_date")
    def _onchange_amount(self):
        igtf_wizards = self.filtered(lambda w: w.is_igtf)
        other_wizards = self - igtf_wizards

        if other_wizards:
            super(AccountPaymentRegisterIgtf, other_wizards)._onchange_amount()

        for payment in igtf_wizards:
            diff = payment.amount - payment.last_computed_amount
            if float_is_zero(diff, precision_rounding=payment.currency_id.rounding):
                continue

            move_ids = self.get_moves()
            igtf = 0.0
            for rec in move_ids:
                igtf += self.calculate_igtf_for_payment(
                    rec, payment.amount, payment.currency_id, payment.payment_date,
                )
            payment.igtf_to_show = abs(igtf)
            payment.igtf_amount = abs(igtf)
            payment.amount_without_difference = payment.amount - abs(igtf)
            payment.last_computed_amount = payment.amount
            payment.custom_user_amount = payment.amount
            payment.custom_user_currency_id = payment.currency_id

    def calculate_igtf_for_payment(self, invoice, amount_payment, payment_currency, payment_date, base=False):
        return self.env["l10n_ve_igtf.utils"].calculate_igtf_for_payment(
            invoice, amount_payment, payment_currency, payment_date, base=base, indexed_default=self.indexed_default
        )

    def convert_to_company_currency(self, from_currency, amount, date):
        self.ensure_one()
        return self.env["l10n_ve_igtf.utils"]._convert_to_company_currency(
            from_currency, amount, date, self.company_id,
        )

    def convert_to_external_currency(self, from_currency, amount, date):
        self.ensure_one()
        return self.env["l10n_ve_igtf.utils"]._convert_to_external_currency(
            from_currency, amount, date, self.company_id,
        )
        
  
    
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
        currency = wizard_values['source_currency_id']

        wizard_values['igtf_amount'] = 0.0
        wizard_values['igtf_percentage'] = self.igtf_percentage
        wizard_values['is_igtf_on_foreign_exchange'] = self.is_igtf_on_foreign_exchange
        
        igtf = 0.0
        final_amount_with_igtf = 0.0
        total_igtf_amount = 0.0
        if create and create.is_igtf:
            if currency != self.env.ref("base.VEF").id:
               
                igtf_for_invoice = self.calculate_igtf_for_payment(
                    invoice_ids, 
                    invoice_ids.amount_residual,
                    self.currency_id,
                    self.payment_date,
                )
                total_igtf_amount += igtf_for_invoice
                base_abs = abs(source_amount)
                final_amount_with_igtf = base_abs + total_igtf_amount
                igtf = self.env["l10n_ve_igtf.utils"]._convert_to_company_currency(
                    invoice_ids.currency_id, total_igtf_amount, self.payment_date, self.company_id,
                )
            else:

                
                currency = self.env['res.currency'].browse(currency)
                source = currency._convert(source_amount, self.currency_id, self.company_id, self.payment_date)
                igtf_for_invoice = self.calculate_igtf_for_payment(
                    invoice_ids, 
                    source,
                    self.currency_id,
                    self.payment_date,
                )
                total_igtf_amount += igtf_for_invoice
                base_abs = abs(source_amount)
                final_amount_with_igtf = base_abs + total_igtf_amount
                igtf = self.env["l10n_ve_igtf.utils"]._convert_to_company_currency(
                    invoice_ids.currency_id, total_igtf_amount, self.payment_date, self.company_id,
                )

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

        currency = batch_values['source_currency_id']
        new_val = False

        if currency != self.currency_id.id:
            currency = self.env['res.currency'].browse(currency)
            source_amount = invoice_ids.amount_residual
            new_val = self.company_id.currency_id._convert(source_amount, self.currency_id, self.company_id, self.payment_date) + batch_values['igtf_amount']

        payment_vals = {
            'date': self.payment_date,
            'amount': new_val if new_val != False else batch_values['source_amount_currency'],
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
            'foreign_rate': self.foreign_rate,
            'foreign_inverse_rate': self.foreign_inverse_rate,
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
        
        payments = super(AccountPaymentRegisterIgtf, self.with_context(skip_account_move_reversal=True))._create_payments()
        
        move_id = (
            self.env.context.get("active_id", False)
        )

        invoice = self.env['account.move'].browse(move_id)

        for payment in payments:
            company_currency = payment.company_id.currency_id
            payment_currency = payment.currency_id
            reconcilable_lines = payment.move_id.line_ids.filtered(
                lambda l: l.account_type in ('asset_receivable', 'liability_payable')
            )
            payment_total_base = payment.move_id.amount_total_signed
            payment_residual_base = reconcilable_lines.amount_residual



            if payment.igtf_amount > 0 and invoice:
                
                igtf_base = payment.currency_id._convert(
                    payment.igtf_amount, company_currency, payment.company_id, payment.date,
                )

                if  abs(payment_residual_base) > 0: #hay residual en el pago
                    supposted_fact_amount = payment_currency.round((abs(payment_total_base) - abs(igtf_base))) #supuesta base de la factura sin igtf
                    #detectamos si lo q queda es el equivalente al igtf o es un apgo mayor
                    
                    if abs(supposted_fact_amount) - abs(invoice.amount_total_signed) <= 0.1: #comparacion si existe una diferencia de decimales por conversion
                        igtf_base = abs(payment_residual_base)
                                                
                debit_note= invoice.prepare_igtf_payment_debit_note(igtf_base, invoice, payment)
                debit_note.with_context(move_action_post_alert=True).action_post()

                debit_note_reconcilable_lines = debit_note.line_ids.filtered(
                    lambda l: l.account_type in ('asset_receivable', 'liability_payable') and not l.reconciled
                )

                if debit_note_reconcilable_lines and reconcilable_lines and abs(reconcilable_lines.amount_residual) > 0.01:
                    debit_note.js_assign_outstanding_line(reconcilable_lines.id)

                   
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

        reconcile = payment.move_id.line_ids.filtered(lambda line: line.account_id.id == partner_account_id)
     
        amount_currency = abs(reconcile.amount_residual_currency)
        amount_bs = abs(reconcile.amount_residual)
        currency = payment.currency_id
       

        
        if abs(amount_currency) != 0.0:
            payment_line_ids = [
                Command.create(
                    {
                        "account_id": advance_account_id,
                        "amount_currency": -amount_currency,
                        "payment_id_advance": payment.id,
                        "currency_id":currency.id,
                        "debit": amount_bs if amount_bs < 0 else 0.0,
                        "credit": abs(amount_bs) if amount_bs > 0 else 0.0,
                    },
                ),
                Command.create(
                    {
                        "account_id": partner_account_id,
                        "amount_currency": amount_currency,
                        "payment_id_advance": payment.id,
                        "currency_id":currency.id,
                        "debit": amount_bs if amount_bs > 0 else 0.0,
                        "credit": abs(amount_bs) if amount_bs < 0 else 0.0,
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
