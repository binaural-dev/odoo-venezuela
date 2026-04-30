from odoo import api, fields, models, _
from odoo.tools.float_utils import float_round

import logging
_logger = logging.getLogger(__name__)

class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"

    def default_alternate_currency(self):
        """
        This method is used to get the foreign currency of the company and set it as the default value of the foreign currency field

        Returns
        -------
        type = int
            The id of the foreign currency of the company

        """
        alternate_currency = self.env.company.currency_foreign_id.id
        if alternate_currency:
            return alternate_currency
        return False

    foreign_currency_id = fields.Many2one(
        "res.currency",
        default=default_alternate_currency,
        
    )

    foreign_rate = fields.Float(
        help="The rate of the payment",
        digits="Tasa",
    )
    foreign_inverse_rate = fields.Float(
        help=(
            "Rate that will be used as factor to multiply of the foreign currency for the payment "
            "and the moves created by the wizard."
        ),
    )
    base_currency_is_vef = fields.Boolean(
        default=lambda self: self.env.company.currency_id == self.env.ref("base.VEF")
    )
    
    first_onchange_executed = fields.Boolean(default=False)
    
    foreign_total_billed_vef = fields.Float(
        string="Total Facturado (VEF)",
        help="Total facturado convertido con la tasa inversa VEF de la fecha seleccionada.",
        store=False,
    )
    
    def default_get(self, fields):
        res = super().default_get(fields)
        active_id = self.env.context.get('active_id')
        if active_id:
            
            move = self.env['account.move'].browse(active_id)
            res['foreign_total_billed_vef'] = move.tax_totals.get('foreign_total_residual') * move.foreign_inverse_rate_vef
        return res

    @api.onchange("foreign_rate")
    def _onchange_foreign_rate(self):
        """
        Onchange the foreign rate and compute the foreign inverse rate
        """
        Rate = self.env["res.currency.rate"]
        for payment in self:
            if not bool(payment.foreign_rate):
                return

            payment.foreign_inverse_rate = Rate.compute_inverse_rate(
                payment.foreign_rate
            )
            

    @api.onchange("payment_date")
    def _onchange_invoice_date(self):
        """
        Onchange the invoice date and compute the foreign rate
        """
        Rate = self.env["res.currency.rate"]
        
        for payment in self:
            if not bool(payment.payment_date):
                return
            rate_values = Rate.compute_rate(
                payment.foreign_currency_id.id, payment.payment_date
            )
            payment.update(rate_values)
<<<<<<< HEAD
            
=======
>>>>>>> 2a749cbe ([FIX] l10n_ve_accountant,l10n_ve_tax:)

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
            }
        )
        return payment_vals


    @api.model
    def _get_wizard_values_from_batch(self, batch_result):
        ''' Extract values from the batch passed as parameter (see '_get_batches')
        to be mounted in the wizard view.
        :param batch_result:    A batch returned by '_get_batches'.
        :return:                A dictionary containing valid fields
        '''
        payment_values = batch_result['payment_values']
        lines = batch_result['lines']
        company = min(lines.company_id, key=lambda c: len(c.sudo().parent_ids))

        source_amount = abs(sum(lines.mapped('amount_residual')))
        if payment_values['currency_id'] == company.currency_id.id:
            source_amount_currency = source_amount
        else:
            source_amount_currency = abs(sum(lines.mapped('amount_residual_currency')))

        return {
            'company_id': company.id,
            'partner_id': payment_values['partner_id'],
            'partner_type': payment_values['partner_type'],
            'payment_type': payment_values['payment_type'],
            'source_currency_id': payment_values['currency_id'],
            'source_amount': source_amount,
            'source_amount_currency': source_amount_currency,
        }
<<<<<<< HEAD
        
        # Inherit exact rates from the invoices if uniformly available
        moves = lines.mapped('move_id')
        if moves:
            rates = set(moves.mapped('foreign_inverse_rate'))
            if len(rates) == 1 and list(rates)[0]:
                res['foreign_inverse_rate'] = list(rates)[0]
                res['foreign_rate'] = moves[0].foreign_rate
                
        return res
    def calculate_amount_foreign(self,source_amount_currency,exact_rate,decimal_places):
        amout = float_round(source_amount_currency * exact_rate, precision_digits=decimal_places)
        return amout
    @api.depends('can_edit_wizard', 'source_amount', 'source_amount_currency', 'source_currency_id', 'company_id', 'currency_id', 'payment_date')
    def _compute_amount(self):
        super()._compute_amount()

        for wizard in self:
            if wizard.currency_id == wizard.company_id.currency_foreign_id:
                
                exact_rate = wizard.foreign_inverse_rate
                if not exact_rate:
                    Rate = self.env["res.currency.rate"]
                    rate_values = Rate.compute_rate(wizard.source_currency_id.id, wizard.payment_date)
                    exact_rate = rate_values.get('foreign_inverse_rate', 0.0)
                
                if exact_rate and wizard.company_id.currency_foreign_id == wizard.currency_id:
                    
                    moves = wizard.line_ids.mapped('move_id')
                    total_foreign_debt = sum(moves.mapped('foreign_amount_residual')) if moves else 0.0
                    
                    if total_foreign_debt:
                        wizard.amount = total_foreign_debt
                    else:
                        wizard.amount = self.calculate_amount_foreign(wizard.source_amount_currency,exact_rate, wizard.currency_id.decimal_places)

    @api.depends('can_edit_wizard', 'amount', 'foreign_inverse_rate')
    def _compute_payment_difference(self):
        super()._compute_payment_difference()
        
        for wizard in self:
            if wizard.can_edit_wizard and wizard.currency_id == wizard.company_id.currency_foreign_id:
                moves = wizard.line_ids.mapped('move_id')
                total_foreign_debt = sum(moves.mapped('foreign_amount_residual')) if moves else 0.0
                
                if total_foreign_debt:
                    wizard.payment_difference = total_foreign_debt - wizard.amount
                else:
                    exact_rate = wizard.foreign_inverse_rate
                    if not exact_rate:
                        Rate = self.env["res.currency.rate"]
                        rate_values = Rate.compute_rate(wizard.source_currency_id.id, wizard.payment_date)
                        exact_rate = rate_values.get('foreign_inverse_rate', 0.0)
                    
                    if exact_rate:
                        exact_debt = float_round(wizard.source_amount_currency, wizard.currency_id.decimal_places) * float_round(exact_rate, wizard.currency_id.decimal_places)
                        wizard.payment_difference = exact_debt - wizard.amount
=======

        if len(lines.move_id) == 1:
            move = lines.move_id
            
            res.update({
                'foreign_rate': move.foreign_rate,
                'foreign_inverse_rate': move.foreign_inverse_rate,
            })
            
        return res
>>>>>>> 2a749cbe ([FIX] l10n_ve_accountant,l10n_ve_tax:)
