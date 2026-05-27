from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class AccountPayment(models.Model):
    _inherit = "account.payment"

    def default_alternate_currency(self):
        """
        This method is used to get the foreign currency of the company and set it as the default
        value of the foreign currency field.

        Returns
        -------
        type = int
            The id of the foreign currency of the company
        """
        return self.env.company.currency_foreign_id.id or False

    foreign_currency_id = fields.Many2one(
        "res.currency", default=default_alternate_currency,
    )

    foreign_rate = fields.Float(
        compute="_compute_rate",
        default=0.0,
        digits="Tasa",
        store=True,
        readonly=False,
    )
    foreign_inverse_rate = fields.Float(
        help="Rate that will be used as factor to multiply of the foreign currency for this move.",
        compute="_compute_rate",
        default=0.0,
        store=True,
        readonly=False,
    )

    concept = fields.Char()

    @api.model_create_multi
    def create(self, vals_list):
        """
        Override the create method to set the rate of the payment to its move.
        """
        payments = super().create(vals_list)
        for payment in payments.with_context(skip_account_move_synchronization=True):
            payment.move_id.write(
                {
                    "foreign_rate": payment.foreign_rate,
                    "foreign_inverse_rate": payment.foreign_inverse_rate,
                }
            )
        return payments

    def _synchronize_to_moves(self, changed_fields):
        """
        Override the _syncrhonize_to_moves method to set the rate of the payment to its move.
        """
        res = super()._synchronize_to_moves(changed_fields)
        if not (
            "foreign_rate" in changed_fields or "foreign_inverse_rate" in changed_fields
        ):
            return
        for payment in self.with_context(skip_account_move_synchronization=True):
            payment.move_id.write(
                {
                    "foreign_rate": payment.foreign_rate,
                    "foreign_inverse_rate": payment.foreign_inverse_rate,
                }
            )
        return res
    

    @api.depends("date")
    def _compute_rate(self):
        """
        Compute the rate of the payment using the compute_rate method of the res.currency.rate model.
        """
        Rate = self.env["res.currency.rate"]
        for payment in self:
            rate_values = Rate.compute_rate(
                payment.foreign_currency_id.id, payment.date or fields.Date.today()
            )
            payment.update(rate_values)

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

    def _prepare_move_line_default_vals(
        self, write_off_line_vals=None, force_balance=None
    ):
        """Override to adjust liquidity and counterpart balances using the Real Portion.

        RATIONALE FOR OVERRIDING (REAL PORTION PAYMENT INTEGRATION):
        Natively, Odoo 17 uses the '_convert' method to determine the 'liquidity_balance', 
        which applies a division-based rate exchange standard. In dual-currency environments 
        with highly fluctuated currencies (e.g., VES/VEF vs USD), rates are stored inversely 
        in the system to preserve precision. Consequently, Odoo's native approach creates 
        a mathematical mismatch by dividing when it should multiply, or vice versa, distorting 
        the final journal entry amounts compared to what the user inputted in the payment form.

        This method intercepts the prepared dictionary list from 'super()' and recalibrates 
        the 'debit' and 'credit' balances dynamically. If the payment currency is the 
        strong foreign control currency (USD), it multiplies by the inverse rate. If the 
        payment currency is the weak local currency (VES/VEF) under a USD base company, 
        it divides. This ensures total mathematical convergence and prevents phantom 
        exchange rate discrepancies between the payment record and the journal entry lines.
        """
        line_vals_list = super(
            AccountPayment, self
        )._prepare_move_line_default_vals(
            write_off_line_vals=write_off_line_vals,
            force_balance=force_balance,
        )

        inverse_rate = (
            self.foreign_inverse_rate
            if hasattr(self, "foreign_inverse_rate") and self.foreign_inverse_rate
            else 0.0
        )
        foreign_currency = self.company_id.currency_foreign_id

        if (
            inverse_rate > 0.0
            and foreign_currency
            and self.currency_id != self.company_id.currency_id
        ):
            for vals in line_vals_list:
                amount_currency = abs(vals.get("amount_currency", 0.0))

                if (
                    self.company_id.currency_id != foreign_currency
                    and self.currency_id == foreign_currency
                ):
                    real_balance = self.company_id.currency_id.round(
                        amount_currency * inverse_rate
                    )

                elif (
                    self.company_id.currency_id == foreign_currency
                    and self.currency_id != foreign_currency
                ):
                    real_balance = self.company_id.currency_id.round(
                        amount_currency / inverse_rate
                    )

                else:
                    continue

                if vals.get("debit", 0.0) > 0.0:
                    vals["debit"] = real_balance
                    vals["credit"] = 0.0
                elif vals.get("credit", 0.0) > 0.0:
                    vals["credit"] = real_balance
                    vals["debit"] = 0.0

        return line_vals_list

    def _create_payment_vals_from_wizard(self, batch_result):
        payment_vals = {
            'date': self.payment_date,
            'amount': self.amount,
            'payment_type': self.payment_type,
            'partner_type': self.partner_type,
            'ref': self.communication,
            'journal_id': self.journal_id.id,
            'company_id': self.company_id.id,
            'currency_id': self.currency_id.id,
            'partner_id': self.partner_id.id,
            'partner_bank_id': self.partner_bank_id.id,
            'payment_method_line_id': self.payment_method_line_id.id,
            'destination_account_id': self.line_ids[0].account_id.id,
            'write_off_line_vals': [],
        }

        if self.payment_difference_handling == 'reconcile':
            if self.early_payment_discount_mode:
                epd_aml_values_list = []
                for aml in batch_result['lines']:
                    if aml.move_id._is_eligible_for_early_payment_discount(self.currency_id, self.payment_date):
                        epd_aml_values_list.append({
                            'aml': aml,
                            'amount_currency': -aml.amount_residual_currency,
                            'balance': aml.currency_id._convert(-aml.amount_residual_currency, aml.company_currency_id, date=self.payment_date,custom_rate =self.foreign_inverse_rate),
                        })

                open_amount_currency = self.payment_difference * (-1 if self.payment_type == 'outbound' else 1)
                open_balance = self.currency_id._convert(open_amount_currency, self.company_id.currency_id, self.company_id, self.payment_date,custom_rate =self.foreign_inverse_rate)
                early_payment_values = self.env['account.move']._get_invoice_counterpart_amls_for_early_payment_discount(epd_aml_values_list, open_balance)
                for aml_values_list in early_payment_values.values():
                    payment_vals['write_off_line_vals'] += aml_values_list

            elif not self.currency_id.is_zero(self.payment_difference):

                if self.writeoff_is_exchange_account:
                    # Force the rate when computing the 'balance' only when the payment has a foreign currency.
                    # If not, the rate is forced during the reconciliation to put the difference directly on the
                    # exchange difference.
                    if self.currency_id != self.company_currency_id:
                        payment_vals['force_balance'] = sum(batch_result['lines'].mapped('amount_residual'))
                else:
                    if self.payment_type == 'inbound':
                        # Receive money.
                        write_off_amount_currency = self.payment_difference
                    else:  # if self.payment_type == 'outbound':
                        # Send money.
                        write_off_amount_currency = -self.payment_difference

                    payment_vals['write_off_line_vals'].append({
                        'name': self.writeoff_label,
                        'account_id': self.writeoff_account_id.id,
                        'partner_id': self.partner_id.iwrite_off_amount_currencyd,
                        'currency_id': self.currency_id.id,
                        'amount_currency': write_off_amount_currency,
                        'balance': self.currency_id._convert(write_off_amount_currency, self.company_id.currency_id, self.company_id, self.payment_date,custom_rate =self.foreign_inverse_rate),
                    })

        return payment_vals