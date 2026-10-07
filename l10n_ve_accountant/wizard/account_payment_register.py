from collections import defaultdict
from odoo import api, fields, models, _
from odoo.tools.float_utils import float_round

import logging
_logger = logging.getLogger(__name__)

class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"

    def default_alternate_currency(self):
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
        compute="_compute_foreign_rate",
        store=True,
        readonly=False,
    )
    foreign_inverse_rate = fields.Float(
        help="Rate that will be used as factor to multiply of the foreign currency for the payment "
             "and the moves created by the wizard.",
        digits=0,
        compute="_compute_foreign_inverse_rate",
        store=True,
        readonly=False,
    )
    base_currency_is_vef = fields.Boolean(
        default=lambda self: self.env.company.currency_id == self.env.ref("base.VEF")
    )
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
            res['foreign_total_billed_vef'] = move.foreign_amount_residual
        return res

    @api.depends("foreign_currency_id", "payment_date")
    def _compute_foreign_rate(self):
        Rate = self.env["res.currency.rate"]
        for payment in self:
            if not bool(payment.payment_date):
                payment.foreign_rate = 0.0
                continue
            rate_values = Rate.compute_rate(
                payment.foreign_currency_id.id, payment.payment_date
            )
            payment.foreign_rate = rate_values.get("foreign_rate", 0.0)

    @api.depends("foreign_rate")
    def _compute_foreign_inverse_rate(self):
        Rate = self.env["res.currency.rate"]
        for payment in self:
            if not bool(payment.foreign_rate):
                payment.foreign_inverse_rate = 0.0
                continue
            payment.foreign_inverse_rate = Rate.compute_inverse_rate(payment.foreign_rate)

  

    @api.depends('can_edit_wizard', 'source_amount', 'source_amount_currency',
                  'source_currency_id', 'company_id', 'currency_id', 'payment_date','foreign_inverse_rate')
    def _compute_amount(self):
        return super()._compute_amount()

    def _get_total_amount_in_wizard_currency_to_full_reconcile(
        self, batch_result, early_payment_discount=True
    ):
        self.ensure_one()
        comp_curr = self.company_id.currency_id
        if self.source_currency_id == self.currency_id:
            return self._get_total_amount_using_same_currency(
                batch_result, early_payment_discount=early_payment_discount
            )
        elif self.source_currency_id != comp_curr and self.currency_id == comp_curr:
            return self.source_currency_id._convert(
                self.source_amount_currency, comp_curr, self.company_id, self.payment_date,
                custom_rate=self.foreign_rate,
            ), False
        elif self.source_currency_id == comp_curr and self.currency_id != comp_curr:
            residual_amount = 0.0
            for aml in batch_result['lines']:
                conversion_date = self.payment_date \
                    if not aml.move_id.payment_id and not aml.move_id.statement_line_id \
                    else aml.date
                residual_amount += comp_curr._convert(
                    aml.amount_residual, self.currency_id,
                    self.company_id, conversion_date,
                    custom_rate=self.foreign_inverse_rate,
                )
            return abs(residual_amount), False
        else:
            return comp_curr._convert(
                self.source_amount, self.currency_id,
                self.company_id, self.payment_date,
                custom_rate=self.foreign_inverse_rate,
            ), False

    def _create_payment_vals_from_wizard(self, batch_result):
        payment_vals = super()._create_payment_vals_from_wizard(batch_result)
        payment_vals.update({
            "foreign_rate": self.foreign_rate,
            "foreign_inverse_rate": self.foreign_inverse_rate,
        })
        if self.writeoff_is_exchange_account and "force_balance" in payment_vals:
            # Core only sends a 'force_balance' when the write-off account is an exchange difference
            # account, but the liquidity line is recomputed with the custom rate of the payment, so
            # that balance is lost and the invoice stays partially paid. Post the difference as an
            # explicit write-off line instead.
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
        custom_rate = 0.0
        if self.foreign_inverse_rate:
            custom_rate = (
                self.foreign_rate
                if self.currency_id == self.foreign_currency_id
                else self.foreign_inverse_rate
            )
        liquidity_balance = sign * abs(self.currency_id._convert(
            abs(self.amount),
            comp_curr,
            self.company_id,
            self.payment_date,
            custom_rate=custom_rate,
        ))
        residual_balance = sum(batch_result["lines"].mapped("amount_residual"))
        return {
            "name": self.writeoff_label,
            "account_id": self.writeoff_account_id.id,
            "partner_id": self.partner_id.id,
            "currency_id": self.currency_id.id,
            "amount_currency": sign * self.payment_difference,
            "balance": comp_curr.round(residual_balance - liquidity_balance),
        }


   