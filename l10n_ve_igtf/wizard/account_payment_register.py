from odoo import api, models, fields, _, Command
from odoo.exceptions import UserError
from odoo.tools import float_is_zero, float_compare
import logging

_logger = logging.getLogger(__name__)


class AccountPaymentRegisterIgtf(models.TransientModel):
    _inherit = "account.payment.register"

    is_igtf = fields.Boolean(
        string="IGTF",
        compute="_compute_check_igtf",
        store=True,
    )

    amount_without_difference = fields.Monetary(
        string="Amount without Difference",
        compute="_compute_amount",
        readonly=False,
    )

    def _default_igtf_percent_from_company(self):
        return self.env.company.igtf_percentage

    igtf_percentage = fields.Float(
        string="IGTF Percentage Aplicado",
        default=_default_igtf_percent_from_company,
        store=True,
    )
    igtf_amount = fields.Float(
        string="IGTF Amount",
        compute="_compute_amount",
        readonly=False,
    )
    igtf_to_show = fields.Monetary(
        string="IGTF to Show",
        compute="_compute_amount",
        readonly=False,
    )
    is_igtf_on_foreign_exchange = fields.Boolean(
        string="IGTF on Foreign Exchange?",
        default=False,
        store=True,
    )
    payment_difference = fields.Monetary(
        compute='_compute_payment_difference',
        readonly=False,
    )
    available_journal_ids = fields.Many2many(
        comodel_name='account.journal',
        compute='_compute_available_journal_ids',
    )
    last_computed_amount = fields.Float("Last Computed Amount")

    def get_moves(self):
        return self.env["l10n_ve_igtf.utils"].get_moves_from_context()

    @api.depends('can_edit_wizard', 'source_amount', 'source_amount_currency', 'source_currency_id',
                 'company_id', 'currency_id', 'payment_date','foreign_inverse_rate','is_igtf')
    def _compute_amount(self):

        for wizard in self:
            if not wizard.journal_id or not wizard.currency_id or not wizard.payment_date:
                if not wizard.is_igtf:
                    wizard.amount = wizard.amount or 0.0
                    wizard.igtf_to_show = 0.0
                    wizard.igtf_amount = 0.0
                wizard.amount_without_difference = 0.0

                
            elif wizard.can_edit_wizard:
                if wizard.amount != wizard.last_computed_amount:
                    total_igtf_amount = 0.0
                    for invoice in wizard.get_moves():
                        if wizard.is_igtf:
                            total_igtf_amount += self.calculate_igtf_for_payment(
                                invoice, wizard.amount, wizard.currency_id, wizard.payment_date,
                            )
                    wizard.igtf_amount = total_igtf_amount
                    wizard.igtf_to_show = total_igtf_amount
                    wizard.amount_without_difference = wizard.amount - abs(total_igtf_amount)
                else:
                    batch_result = wizard._get_batches()[0]
                    base_amount = wizard._get_total_amount_in_wizard_currency_to_full_reconcile(
                        batch_result, early_payment_discount=False
                    )[0]or 0.0

                    total_igtf_amount = 0.0
                    for invoice in wizard.get_moves():
                        if wizard.is_igtf:
                            total_igtf_amount += self.calculate_igtf_for_payment(
                                invoice, base_amount, wizard.currency_id, wizard.payment_date,
                            )

                    wizard.amount = base_amount + total_igtf_amount
                    wizard.igtf_amount = total_igtf_amount
                    wizard.igtf_to_show = total_igtf_amount
                    wizard.amount_without_difference = base_amount

                wizard.last_computed_amount = wizard.amount

    @api.depends('can_edit_wizard', 'amount', 'payment_date', 'is_igtf','amount_without_difference')
    def _compute_payment_difference(self):
        igtf_wizards = self.filtered(lambda w: w.is_igtf)
        other_wizards = self - igtf_wizards

        for wizard in igtf_wizards:
            if not wizard.can_edit_wizard or not wizard.payment_date:
                continue
            currency = wizard.currency_id
            batch_result = wizard._get_batches()[0]
            total_residual = wizard._get_total_amount_in_wizard_currency_to_full_reconcile(
                batch_result, early_payment_discount=False
            )[0]
            expected_amount = total_residual + wizard.igtf_to_show
            raw_difference = expected_amount - wizard.amount
            if abs(raw_difference) < currency.rounding:
                wizard.payment_difference = 0.0
            else:
                wizard.payment_difference = raw_difference

        if other_wizards:
            return super(AccountPaymentRegisterIgtf, other_wizards)._compute_payment_difference()

    @api.depends("journal_id", "currency_id")
    def _compute_check_igtf(self):
        for payment in self:
            payment.is_igtf = False
            payment.is_igtf_on_foreign_exchange = False
            if payment.journal_id.is_igtf and not payment.journal_id.is_purchase_international:
                for move_id in payment.get_moves():
                    if move_id.journal_id.is_purchase_international:
                        continue
                    if payment.partner_id._check_igtf_apply_improved(move_id) \
                            and payment.currency_id != payment.env.ref("base.VEF"):
                        payment.is_igtf = True
                        payment.is_igtf_on_foreign_exchange = True

    @api.onchange("amount", "payment_date")
    def _onchange_amount(self):
        
        for payment in self:
            if not payment.is_igtf:
                continue
            diff = payment.amount - payment.last_computed_amount
            if float_is_zero(diff, precision_rounding=payment.currency_id.rounding):
                continue
            
            total_igtf_amount = 0.0
            for invoice in payment.get_moves():
                total_igtf_amount += self.calculate_igtf_for_payment(
                    invoice, payment.amount, payment.currency_id, payment.payment_date,
                )
            payment.igtf_to_show = abs(total_igtf_amount)
            payment.igtf_amount = abs(total_igtf_amount)
            payment.amount_without_difference = payment.amount - abs(total_igtf_amount)

    def calculate_igtf_for_payment(self, invoice, amount_payment, payment_currency, payment_date):
        return self.env["l10n_ve_igtf.utils"].calculate_igtf_for_payment(
            invoice, amount_payment, payment_currency, payment_date,
        )

    @api.depends('available_journal_ids')
    def _compute_journal_id(self):
        for wizard in self:
            if wizard.can_edit_wizard:
                batch = wizard._get_batches()[0]
                wizard.journal_id = wizard._get_batch_journal(batch)
            else:
                wizard.journal_id = self.env['account.journal'].search([
                    *self.env['account.journal']._check_company_domain(wizard.company_id),
                    ('type', 'in', ('bank', 'cash')),
                    ('is_igtf', '!=', True),
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

      
        
        if create and create.journal_id.is_igtf:
            total_igtf_amount = 0.0
        
            move_ids = lines.mapped('move_id')
            for invoice in move_ids:
                igtf_for_invoice = self.calculate_igtf_for_payment(
                    invoice,
                    invoice.amount_residual,
                    create.currency_id,
                    create.payment_date,
                )
                total_igtf_amount += igtf_for_invoice
            base_abs = abs(source_amount)
            final_amount_with_igtf = (base_abs + total_igtf_amount) 
            
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
        lines = batch_result['lines']
        payment_vals.update({
            "igtf_amount": self.igtf_amount,
            "payment_from_wizard": True,
            "igtf_percentage": self.igtf_percentage,
            "is_igtf_on_foreign_exchange": self.is_igtf_on_foreign_exchange,
            "invoices_origin_ids": [Command.set(lines.mapped('move_id').ids)],
        })
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
                        'balance': currency._convert(-aml.amount_residual_currency, aml.company_currency_id, self.company_id, self.payment_date,self.foreign_inverse_rate),
                    })

            open_amount_currency = (batch_values['source_amount_currency'] - total_amount) * (-1 if batch_values['payment_type'] == 'outbound' else 1)
            open_balance = currency._convert(open_amount_currency, aml.company_currency_id, self.company_id, self.payment_date,self.foreign_inverse_rate)
            early_payment_values = self.env['account.move']\
                ._get_invoice_counterpart_amls_for_early_payment_discount(epd_aml_values_list, open_balance)
            for aml_values_list in early_payment_values.values():
                payment_vals['write_off_line_vals'] += aml_values_list
        return payment_vals

    
