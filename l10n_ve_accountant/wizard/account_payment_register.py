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
        rate_values = Rate.compute_rate(self.foreign_currency_id.id, self.payment_date)
        self.foreign_inverse_rate = rate_values.get("foreign_inverse_rate")  
            

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
        if self.writeoff_is_exchange_account and "force_balance" in payment_vals:
            # Core only sends a 'force_balance' when the write-off account is an exchange difference
            # account, but it can be lost by other overrides of the payment move lines, so the
            # invoice stays partially paid. Post the difference as an explicit write-off line instead.
            payment_vals.pop("force_balance")
            payment_vals["write_off_line_vals"].append(
                self._prepare_exchange_difference_write_off_vals(batch_result)
            )
        return payment_vals

    def _prepare_exchange_difference_write_off_vals(self, batch_result):
        """
        Build the write-off line of the exchange difference so the counterpart line of the payment
        matches exactly the residual of the invoices in company currency.

        The liquidity balance is computed the same way as in account.payment
        _prepare_move_line_default_vals, so the counterpart line ends up being equal to the residual
        and the invoices are fully reconciled without leaving any remaining cents.
        """
        self.ensure_one()
        comp_curr = self.company_id.currency_id
        sign = 1 if self.payment_type == "inbound" else -1
        liquidity_balance = sign * abs(self.currency_id._convert(
            abs(self.amount),
            comp_curr,
            self.company_id,
            self.payment_date,
        ))
        residual_balance = sum(batch_result["lines"].mapped("amount_residual"))
        return {
            "name": self.writeoff_label,
            "account_id": self.writeoff_account_id.id,
            "partner_id": self.partner_id.id,
            "currency_id": self.currency_id.id,
            "amount_currency": sign * self.payment_difference,
            "balance": residual_balance - liquidity_balance,
        }


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
