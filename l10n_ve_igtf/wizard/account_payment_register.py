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

    amount_without_difference = fields.Float(
        string="Amount without Difference",
    )

    payment_difference = fields.Monetary(
        compute='_compute_payment_difference',readonly=False)


    igtf_to_show = fields.Float(string="Amount with IGTF")

    available_journal_ids = fields.Many2many(
        comodel_name='account.journal',
        compute='_compute_available_journal_ids'
    )

    last_computed_amount = fields.Float("Last Computed Amount", digits=(16, 2))


    @api.depends('can_edit_wizard', 'source_amount', 'source_amount_currency', 'source_currency_id', 'company_id', 'currency_id', 'payment_date')
    def _compute_amount(self):
        
        for wizard in self:
            
            base_amount = 0.0
            if not wizard.journal_id or not wizard.currency_id or not wizard.payment_date:
                base_amount = wizard.amount or 0.0
            elif wizard.source_currency_id and wizard.can_edit_wizard:
                batch_result = wizard._get_batches()[0]
                base_amount = wizard._get_total_amount_in_wizard_currency_to_full_reconcile(batch_result)[0] or 0.0
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
                        wizard.igtf_percentage
                    )

                    total_igtf_amount += igtf_for_invoice
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
                batch_result = wizard._get_batches()[0]
                
                total_residual = wizard\
                    ._get_total_amount_in_wizard_currency_to_full_reconcile(batch_result, early_payment_discount=False)[0]

                expected_amount = total_residual

                
                if wizard.is_igtf and float_compare(wizard.igtf_to_show, 0.0, precision_rounding=precision) > 0.0:

                    expected_amount += wizard.igtf_to_show
                raw_difference = expected_amount - wizard.amount
                
                rounded_difference = raw_difference
                
                if abs(rounded_difference) < wizard.currency_id.rounding:
                    wizard.payment_difference = 0.0
                else:
                    wizard.payment_difference = rounded_difference
       
    @api.onchange("igtf_to_show")
    def _compute_amount_without_difference(self):
        for rec in self:
            
            amount_without_difference = 0.0

            move_ids=self.get_moves()
            for move_id in move_ids:
                
                if rec.company_currency_id and rec.company_currency_id != self.env.ref("base.VEF"):
                    if rec.amount <= move_id.amount_residual + move_id.amount_residual * (rec.igtf_percentage / 100):
                        amount_without_difference = amount_without_difference + (rec.amount - rec.igtf_to_show)
                    
                    elif rec.amount > move_id.amount_residual + move_id.amount_residual * (rec.igtf_percentage / 100) :
                        amount_without_difference = amount_without_difference + move_id.amount_residual   
                else:
                    if rec.amount <= move_id.foreign_amount_residual + move_id.foreign_amount_residual * (rec.igtf_percentage / 100):
                        amount_without_difference = amount_without_difference + (rec.amount - rec.igtf_to_show)
                    
                    elif rec.amount > move_id.foreign_amount_residual + move_id.foreign_amount_residual * (rec.igtf_percentage / 100) :
                        amount_without_difference = amount_without_difference + move_id.foreign_amount_residual  
            rec.amount_without_difference = amount_without_difference
                             

    @api.onchange("journal_id","currency_id")
    def _compute_check_igtf(self):
        """ Check if the company is a ordinary contributor"""
        for payment in self:
            payment.is_igtf = False
            if payment.journal_id.is_igtf and payment.partner_id:
                move_ids=self.get_moves()
                for move_id in move_ids:
                    if payment.partner_id._check_igtf_apply_improved(move_id.move_type):
                        payment.is_igtf = True

                   
                        
    @api.onchange("is_igtf", "igtf_to_show")
    def _compute_amount_with_igtf(self):
        """Compute the amount with igtf of the payment"""
        for payment in self:
            if payment.is_igtf:
                payment.amount_with_igtf = payment.amount + payment.igtf_to_show

    @api.onchange("amount")
    def _compute_igtf_amount(self):
        for payment in self:
            
            diff = payment.amount - payment.last_computed_amount
            if float_is_zero(diff, precision_rounding=payment.currency_id.rounding):
                return
            move_ids=self.get_moves()

            amount = False
           
            for rec in move_ids:
                if payment.is_igtf:
                    invoice = rec
                   
                    amount = amount + payment.calculate_igtf_for_payment(invoice, payment.amount, payment.igtf_percentage)
            if payment.is_igtf:
                payment.igtf_to_show = amount
                payment.igtf_amount = amount
                
            else:
                payment.igtf_to_show = 0.0
                payment.igtf_amount = 0.0

            payment.last_computed_amount = payment.amount

    def calculate_igtf_for_payment(self, invoice, payment_amount, igtf_percentage=False):
        self.ensure_one()
        
        currency = self.currency_id
        precision = currency.rounding
        
        principal_debt = invoice.amount_residual if invoice.company_currency_id != self.env.ref("base.VEF") else invoice.foreign_amount_residual

        principal_amount = min(payment_amount, principal_debt)
        

        igtf_unrounded = principal_amount * (self.env.company.igtf_percentage / 100)

        igtf_top = invoice.igtf_top_aply

        alter_bi_igtf = invoice.alter_bi_igtf

        igtf= igtf_unrounded

        invoice_residual = invoice.amount_residual if self.company_currency_id != self.env.ref("base.VEF") else invoice.foreign_amount_residual
    
        if not float_is_zero(igtf, precision_rounding=precision) and igtf_top == invoice_residual:
            
            return 0.0
        
        if float_compare(igtf_top, 0.0, precision_rounding=precision) >= 0.0 and float_compare(igtf, igtf_top, precision_rounding=precision) > 0.0:
            
            return 0.0
        

        residual_igtf = igtf_top - alter_bi_igtf

        
        if igtf > residual_igtf and  not float_is_zero(residual_igtf, precision_rounding=precision):
            igtf = residual_igtf
        
        return igtf
        
    @api.onchange('journal_id')
    def _compute_is_igtf_journal(self):
        for record in self:
            if record.journal_id.currency_id and record.journal_id.currency_id == self.env.ref("base.USD"):
                record.is_igtf_on_foreign_exchange = True
            else:
                record.is_igtf_on_foreign_exchange = False
    
    @api.depends('available_journal_ids')
    def _compute_journal_id(self):
        for wizard in self:
            if wizard.can_edit_wizard:
                batch = wizard._get_batches()[0]
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
            ('type', 'in', ('bank', 'cash')),
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
    def _get_wizard_values_from_batch(self, batch_result, create=False):
        
        wizard_values = super()._get_wizard_values_from_batch(batch_result)
        source_amount = wizard_values['source_amount'] 
        
        lines = batch_result['lines']

        sign = -1 if wizard_values.get('payment_type') == 'outbound' else 1
        
        if create and create.journal_id.is_igtf:
            total_igtf_amount = 0.0
        
            move_ids = lines.mapped('move_id')
            for invoice in move_ids:
                igtf_for_invoice = self.calculate_igtf_for_payment(
                    invoice, 
                    invoice.amount_residual, 
                    self.igtf_percentage
                )
                total_igtf_amount += igtf_for_invoice
            base_abs = abs(source_amount)
            final_amount_with_igtf = (base_abs + total_igtf_amount) * sign
            
            wizard_values['source_amount'] = final_amount_with_igtf
            wizard_values['source_amount_currency'] = final_amount_with_igtf
            wizard_values['igtf_amount'] = total_igtf_amount
            wizard_values['payment_from_wizard'] = True
            wizard_values['igtf_percentage'] = create.igtf_percentage
            wizard_values['is_igtf_on_foreign_exchange'] = create.is_igtf_on_foreign_exchange
            
        return wizard_values
    
    def _create_payment_vals_from_wizard(self, batch_result):
        """
        This method is used to add the foreign rate and the foreign inverse rate to the payment
        values that are used to create the payment from the wizard.
        """
        payment_vals = super()._create_payment_vals_from_wizard(batch_result)
        payment_vals.update(
            {
                "foreign_rate": self.foreign_rate,
                "foreign_inverse_rate": self.foreign_inverse_rate,
                "igtf_amount": self.igtf_amount,
                "payment_from_wizard": True,
                "igtf_percentage": self.igtf_percentage,
                "is_igtf_on_foreign_exchange": self.is_igtf_on_foreign_exchange
            }
        )
        return payment_vals
   
    def _create_payment_vals_from_batch(self, batch_result):
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
            'ref': self._get_batch_communication(batch_result),
            'journal_id': self.journal_id.id,
            'company_id': self.company_id.id,
            'currency_id': batch_values['source_currency_id'],
            'partner_id': batch_values['partner_id'],
            'igtf_amount': batch_values['igtf_amount'],
            'payment_from_wizard': True,
            'igtf_percentage': batch_values['igtf_percentage'],
            'is_igtf_on_foreign_exchange': batch_values['is_igtf_on_foreign_exchange'],
            'payment_method_line_id': payment_method_line.id,
            'destination_account_id': batch_result['lines'][0].account_id.id,
            'write_off_line_vals': [],
        }

        if partner_bank_id:
            payment_vals['partner_bank_id'] = partner_bank_id

        total_amount, mode = self._get_total_amount_using_same_currency(batch_result)
        currency = self.env['res.currency'].browse(batch_values['source_currency_id'])
        if mode == 'early_payment':
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
