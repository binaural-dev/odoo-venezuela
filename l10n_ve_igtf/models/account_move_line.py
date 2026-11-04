import math

from odoo import api, fields, models, _
from odoo.exceptions import UserError

import logging

_logger = logging.getLogger(__name__)
class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    payment_id_advance = fields.Many2one(
        "account.payment",
        string="Payment Advance"
    )

    @api.model
    def _l10n_ve_offers_widget_residual(self, aml, counterpart_currency):
        """True si la línea ofrece residual en la moneda de la contraparte (cruce desde el widget).
        Aplica si una de las dos monedas es la de la compañía, o ninguna (tercera moneda)."""
        company_currency = aml.company_currency_id
        return counterpart_currency != aml.currency_id and (
            aml.currency_id == company_currency or counterpart_currency != company_currency
        )

    @api.model
    def _l10n_ve_widget_residual(self, aml_values, counterpart_currency, widget_rate):
        """Residual de la línea en la moneda de la contraparte, valorado con la tasa del widget.
        `widget_rate`: moneda de la contraparte por unidad de la moneda de la línea; el motor
        espera la tasa por Bs."""
        aml = aml_values['aml']
        remaining = aml_values['amount_residual']
        in_company_currency = aml.currency_id == aml.company_currency_id
        base = abs(remaining if in_company_currency else aml_values['amount_residual_currency'])
        residual = counterpart_currency.round(base * widget_rate)
        if not (remaining and residual):
            return {}
        return {counterpart_currency: {
            'residual': math.copysign(residual, remaining),
            'rate': widget_rate if in_company_currency else residual / abs(remaining),
        }}

    @api.model
    def _prepare_move_line_residual_amounts(self, aml_values, counterpart_currency, shadowed_aml_values=None, other_aml_values=None):
        """The core doesn't recognize an "advance cross" move
        (`is_advance_move=True`) as a real payment, so it would rate the
        reconciliation at the invoice date's rate instead of the cross's
        real one. Forcing `forced_rate_from_register_payment` -- the same
        hook core's own payment-register wizard uses -- makes core's
        unmodified `get_odoo_rate()` pick it up immediately (first line of
        that closure), without copying the rest of the method.
        """
        aml = aml_values['aml']
        other_aml = (other_aml_values or {}).get('aml')
        widget_rate = (self.env.context.get('l10n_ve_widget_rates') or {}).get(aml.id)
        if widget_rate and self._l10n_ve_offers_widget_residual(aml, counterpart_currency):
            result = super()._prepare_move_line_residual_amounts(
                aml_values, counterpart_currency,
                shadowed_aml_values=shadowed_aml_values, other_aml_values=other_aml_values,
            )
            result.update(self._l10n_ve_widget_residual(aml_values, counterpart_currency, widget_rate))
            return result
        if (
            other_aml
            and other_aml.move_id.is_advance_move
            and not (aml.move_id.origin_payment_id or aml.move_id.statement_line_id or aml.move_id.is_advance_move)
            and not self.env.context.get('forced_rate_from_register_payment')
        ):
            balance = other_aml._get_reconciliation_aml_field_value('balance', shadowed_aml_values)
            amount_currency = other_aml._get_reconciliation_aml_field_value('amount_currency', shadowed_aml_values)
            if not other_aml.company_currency_id.is_zero(balance) and not counterpart_currency.is_zero(amount_currency):
                self = self.with_context(forced_rate_from_register_payment=abs(amount_currency / balance))
        return super()._prepare_move_line_residual_amounts(
            aml_values, counterpart_currency,
            shadowed_aml_values=shadowed_aml_values,
            other_aml_values=other_aml_values,
        )


    def action_register_payment(self):
        """ 
        # 1. Validate Unique Partner
        # 2. Validate Unique Currency
        # 3. Optional: Validate Unique Company (Best practice for Multi-company)
        # If all validations pass, call the original Odoo function"""

        partners = self.mapped('partner_id')
        if len(partners) > 1:
            raise UserError(_("You cannot register payments for different partners at the same time. "
                              "Please select invoices belonging to a single contact."))

       
        currencies = self.mapped('move_id.currency_id')
        if len(currencies) > 1:
            raise UserError(_("You cannot register payments with multiple currencies. "
                              "All selected invoices must have the same currency."))
        
        
        companies = self.mapped('move_id.company_id')
        if len(companies) > 1:
            raise UserError(_("You cannot register payments for different companies at the same time."))

        
        return super(AccountMoveLine, self).action_register_payment()

    @api.model
    def _prepare_reconciliation_single_partial(self, debit_values, credit_values, shadowed_aml_values=None, **kwargs):
        """Pago en una tercera moneda conciliado en la moneda de la factura: reexpresa en su propia
        moneda el monto en divisa del parcial (el core lo asume en la de conciliación) y corrige
        su residual. Usa la misma tasa del widget (`l10n_ve_widget_rates`); ver
        `_l10n_ve_widget_residual`."""
        rates = self.env.context.get('l10n_ve_widget_rates') or {}
        third = [
            (values, side)
            for values, side in ((debit_values, 'debit'), (credit_values, 'credit'))
            if values['aml'].id in rates and values['aml'].currency_id != values['aml'].company_currency_id
        ]
        residual_before = {side: values['amount_residual_currency'] for values, side in third}
        res = super()._prepare_reconciliation_single_partial(
            debit_values, credit_values, shadowed_aml_values=shadowed_aml_values, **kwargs
        )
        partial = (res or {}).get('partial_values')
        if not partial:
            return res
        for values, side in third:
            aml = values['aml']
            other = credit_values['aml'] if side == 'debit' else debit_values['aml']
            if other.currency_id in (aml.company_currency_id, aml.currency_id):
                continue
            currency = aml.currency_id
            rate = rates[aml.id]
            before = residual_before[side]
            applied = partial[f'{side}_amount_currency']
            if other.currency_id.is_zero(applied - other.currency_id.round(abs(before) * rate)):
                consumed = abs(before)
            else:
                consumed = min(abs(before), currency.round(applied / rate))
            partial[f'{side}_amount_currency'] = consumed
            values['amount_residual_currency'] = before + consumed if side == 'credit' else before - consumed
            fully_consumed = (
                currency.is_zero(values['amount_residual_currency'])
                and aml.company_currency_id.is_zero(values['amount_residual'])
            )
            res[f'{side}_values'] = None if fully_consumed else values
        return res
