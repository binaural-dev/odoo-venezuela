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
        digits=(16, 15),
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

            batch_result = payment._get_batches()[0]
            payment.foreign_inverse_rate = Rate.compute_inverse_rate(
                payment.foreign_rate
            )
            total_amount_residual_in_wizard_currency = (
                payment._get_total_amount_in_wizard_currency_to_full_reconcile(
                    batch_result, early_payment_discount=False
                )[0]
            )
            payment.amount = total_amount_residual_in_wizard_currency

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

    @api.depends("can_edit_wizard", "amount", "foreign_inverse_rate")
    def _compute_payment_difference(self):
        for wizard in self:
            if wizard.can_edit_wizard:
                batch_result = wizard._get_batches()[0]
                total_amount_residual_in_wizard_currency = (
                    wizard._get_total_amount_in_wizard_currency_to_full_reconcile(
                        batch_result, early_payment_discount=False
                    )[0]
                )
                wizard.payment_difference = (
                    total_amount_residual_in_wizard_currency - wizard.amount
                )
            else:
                wizard.payment_difference = 0.0



    @api.model
    def _get_wizard_values_from_batch(self, batch_result):
        ''' Extract values from the batch passed as parameter (see '_get_batches')
        to be mounted in the wizard view.
        :param batch_result:    A batch returned by '_get_batches'.
        :return:                A dictionary containing valid fields
        '''
        payment_values = batch_result['payment_values']
        lines = batch_result['lines']
        company = min(lines.company_id, key=lambda c: len(c.sudo().parent_ids)) if not self._from_sibling_companies(lines) else lines.company_id.root_id

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

    @api.depends('can_edit_wizard', 'source_amount', 'source_amount_currency', 'source_currency_id', 'company_id', 'currency_id', 'payment_date')
    def _compute_amount(self):
        super()._compute_amount()

        for wizard in self:

            if not wizard.is_igtf and wizard.currency_id == wizard.company_id.currency_foreign_id:
                exact_rate = wizard.foreign_inverse_rate
                if not exact_rate:
                    Rate = self.env["res.currency.rate"]
                    rate_values = Rate.compute_rate(wizard.source_currency_id.id, wizard.payment_date)
                    exact_rate = rate_values.get('foreign_inverse_rate', 0.0)
                
                if exact_rate:
                    exact_amount = round(wizard.source_amount_currency, wizard.currency_id.decimal_places) * round(exact_rate, wizard.currency_id.decimal_places)
                    wizard.amount = exact_amount
