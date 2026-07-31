import inspect
from contextlib import contextmanager
from odoo import api, fields, models, Command, _
from odoo.tools import float_compare
from odoo.exceptions import UserError, ValidationError
from odoo.tools import frozendict, formatLang, format_date, Query, float_round

from datetime import date, timedelta
import traceback
from markupsafe import Markup
from odoo.tools import float_is_zero

import logging

_logger = logging.getLogger(__name__)

class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    not_foreign_recalculate = fields.Boolean()
    foreign_currency_id = fields.Many2one(
        related="move_id.foreign_currency_id", store=True
    )
    foreign_rate = fields.Float(related="move_id.foreign_rate", store=True)
    foreign_inverse_rate = fields.Float(
        related="move_id.foreign_inverse_rate", store=True, index=True
    )

    foreign_price_manual = fields.Boolean(
        default=False,
        help="Indicates that foreign_price was manually set and should be preserved.",
    )
    foreign_price = fields.Monetary(
        help="Foreign Price of the line",
        compute="_compute_foreign_price",
        inverse="_inverse_foreign_price",
        currency_field="foreign_currency_id",
        store=True,
        copy=True
    )
    foreign_subtotal = fields.Monetary(
        help="Foreign Subtotal of the line",
        compute="_compute_foreign_subtotal",
        currency_field="foreign_currency_id",
        store=True,
    )
    foreign_price_total = fields.Monetary(
        help="Foreign Total of the line",
        compute="_compute_foreign_subtotal",
        currency_field="foreign_currency_id",
        store=True,
    )
    amount_currency = fields.Monetary(precompute=False)

    # Report fields
    foreign_debit = fields.Monetary(
        currency_field="foreign_currency_id",
        compute="_compute_foreign_debit_credit",
        store=True,
        readonly=False
        
    )
    foreign_credit = fields.Monetary(
        currency_field="foreign_currency_id",
        compute="_compute_foreign_debit_credit",
        store=True,
        readonly=False
    )

    foreign_debit_no_format = fields.Float()
    foreign_credit_no_format = fields.Float()

    foreign_balance = fields.Monetary(
        currency_field="foreign_currency_id",
        compute="_compute_foreign_balance",
        inverse="_inverse_foreign_balance",
        store=True,
    )

    foreign_debit_adjustment = fields.Monetary(
        currency_field="foreign_currency_id",
        help="When setted, this field will be used to fill the foreign debit field",
    )
    foreign_credit_adjustment = fields.Monetary(
        currency_field="foreign_currency_id",
        help="When setted, this field will be used to fill the foreign credit field",
    )

    foreign_amount_residual = fields.Monetary(
        currency_field="foreign_currency_id",
        compute="_compute_foreign_amount_residual",
        store=True,
        readonly=True,
    )
    foreign_amount_residual_currency = fields.Monetary(
        currency_field="foreign_currency_id",
        compute="_compute_foreign_amount_residual",
        store=True,
        readonly=True,
    )


    @api.depends("product_id", "move_id.name")
    def _compute_name(self):
        lines_without_name = self.filtered(lambda l: not l.name)
        res = super(AccountMoveLine, lines_without_name)._compute_name()
        for line in self.filtered(
            lambda l: l.move_type in ("out_invoice", "out_receipt")
            and l.account_id.account_type == "asset_receivable"
        ):
            line.name = line.move_id.name
        return res

    @api.depends("price_unit", "foreign_inverse_rate", "currency_id",
                  "move_id.foreign_inverse_rate")
    def _compute_foreign_price(self):
        for line in self:
            if line.foreign_price_manual:
                continue
            else:
                line.foreign_price = line.currency_id._convert(
                    line.price_unit,
                    line.foreign_currency_id,
                    line.company_id,
                    line.move_id.invoice_date or fields.Date.today(),
                    custom_rate=line.foreign_inverse_rate
                )

    def _inverse_foreign_price(self):
        for line in self:
            if not (line.currency_id and line.foreign_currency_id and line.company_id):
                line.foreign_price_manual = True
                continue
            expected = line.currency_id._convert(
                line.price_unit,
                line.foreign_currency_id,
                line.company_id,
                line.move_id.invoice_date or fields.Date.today(),
                custom_rate=line.foreign_inverse_rate,
            )
            if line.foreign_currency_id.compare_amounts(line.foreign_price, expected) != 0:
                line.foreign_price_manual = True

    @api.depends("foreign_price", "quantity", "discount", "tax_ids", "price_unit")
    def _compute_foreign_subtotal(self):
        for line in self:
            line_discount_price_unit = line.foreign_price * (
                1 - (line.discount / 100.0)
            )
            foreign_subtotal = line_discount_price_unit * line.quantity

            if line.tax_ids:
                taxes_res = line.tax_ids.compute_all(
                    line_discount_price_unit,
                    quantity=line.quantity,
                    currency=line.foreign_currency_id,
                    product=line.product_id,
                    partner=line.partner_id,
                    is_refund=line.is_refund,
                )
                line.foreign_subtotal = taxes_res["total_excluded"]
                line.foreign_price_total = taxes_res["total_included"]
            else:
                line.foreign_price_total = line.foreign_subtotal = foreign_subtotal

    def _set_foreign(self, value):
        self.foreign_debit = abs(value) if value > 0 else 0.0
        self.foreign_credit = abs(value) if value < 0 else 0.0

    def _get_non_invoice_foreign_value(self):
        foreign_lines = self.move_id.line_ids.filtered(
            lambda l: l.currency_id == l.company_id.currency_foreign_id
        )
        currency_lines = self.move_id.line_ids.filtered(
            lambda l: l.currency_id == l.company_id.currency_id
        )
        balance = sum(foreign_lines.mapped("amount_currency"))
        if balance and len(currency_lines) == 1:
            return -balance

        cur = self.currency_id
        if cur and cur != self.company_id.currency_foreign_id and cur != self.company_id.currency_id:
            return self.company_id.currency_id._convert(
                self.debit - self.credit,
                self.company_id.currency_foreign_id,
                self.company_id,
                self.date or fields.Date.context_today(self),
            )

        return (self.debit - self.credit) * self.foreign_inverse_rate

    def _get_foreign_value(self):
        self.ensure_one()

        if self.display_type in ("payment_term", "tax"):
            if self.foreign_debit_adjustment:
                return abs(self.foreign_debit_adjustment)
            if self.foreign_credit_adjustment:
                return -abs(self.foreign_credit_adjustment)
            return self.foreign_balance

        if self.display_type in ("line_section", "line_note"):
            return 0.0

        if self.foreign_debit_adjustment:
            return abs(self.foreign_debit_adjustment)

        if self.foreign_credit_adjustment:
            return -abs(self.foreign_credit_adjustment)

        if self.currency_id == self.company_id.currency_foreign_id and self.amount_currency:
            return self.amount_currency

        if self.move_id.payment_id \
                and "retention_foreign_amount" in self.env["account.payment"]._fields \
                and self.move_id.payment_id.is_retention:
            retention_amount = self.move_id.payment_id.retention_foreign_amount
            if self.credit:
                return retention_amount
            return -retention_amount

        if not self.move_id.is_invoice(include_receipts=True):
            return self._get_non_invoice_foreign_value()

        if self.display_type in ("product", "cogs"):
            sign = self.move_id.direction_sign * -1
            return -(self.foreign_subtotal * sign)

        return (self.debit - self.credit) * self.foreign_inverse_rate

    def _skip_foreign_compute(self):
        return (
            self.move_id.journal_id == self.company_id.currency_exchange_journal_id
            or self.not_foreign_recalculate
        )

    @api.depends(
        "debit",
        "credit",
        "foreign_subtotal",
        "foreign_balance",
        "amount_currency",
        "not_foreign_recalculate",
        "foreign_debit_adjustment",
        "foreign_credit_adjustment",
        "foreign_inverse_rate",
        "move_id.foreign_inverse_rate",
    )
    def _compute_foreign_debit_credit(self):
        for line in self:
            if line._skip_foreign_compute():
                continue
            value = line._get_foreign_value()
            if value is not None:
                line._set_foreign(value)
        
    @api.depends("foreign_credit", "foreign_debit")
    def _compute_foreign_balance(self):
        for line in self:
        
            line.foreign_balance = line.foreign_debit - line.foreign_credit

    def _inverse_foreign_balance(self):
        for line in self:
            line.foreign_debit = (
                abs(line.foreign_balance) if line.foreign_balance > 0 else 0.0
            )
            line.foreign_credit = (
                abs(line.foreign_balance) if line.foreign_balance < 0 else 0.0
            )


    def _prepare_analytic_distribution_line(
        self, distribution, account_id, distribution_on_each_plan
        ):
        """
        This method adds the foreign_amount in the foreign currency to the analytical account line
        """
        self.ensure_one()
        res = super()._prepare_analytic_distribution_line(
            distribution, account_id, distribution_on_each_plan
        )
        account_id = int(account_id)
        account = self.env["account.analytic.account"].browse(account_id)
        distribution_plan = (
            distribution_on_each_plan.get(account.root_plan_id, 0) + distribution
        )
        decimal_precision = self.env["decimal.precision"].precision_get(
            "Percentage Analytic"
        )
        if (
            float_compare(distribution_plan, 100, precision_digits=decimal_precision)
            == 0
        ):
            foreign_amount = (
                -self.foreign_balance
                * (100 - distribution_on_each_plan.get(account.root_plan_id, 0))
                / 100.0
            )
        else:
            foreign_amount = -self.foreign_balance * distribution / 100.0

        res["foreign_amount"] = foreign_amount
        return res

    @api.model
    def _prepare_move_line_residual_amounts(
        self,
        aml_values,
        counterpart_currency,
        shadowed_aml_values=None,
        other_aml_values=None,
    ):
        """Prepare the available residual amounts for each currency.
        :param aml_values: The values of account.move.line to consider.
        :param counterpart_currency: The currency of the opposite line this line will be reconciled with.
        :param shadowed_aml_values: A mapping aml -> dictionary to replace some original aml values to something else.
                                    This is usefull if you want to preview the reconciliation before doing some changes
                                    on amls like changing a date or an account.
        :param other_aml_values:    The other aml values to be reconciled with the current one.
        :return: A mapping currency -> dictionary containing:
            * residual: The residual amount left for this currency.
            * rate:     The rate applied regarding the company's currency.
        """

        def is_payment(aml):
            return aml.move_id.payment_id or aml.move_id.statement_line_id

        def get_odoo_rate(aml, other_aml, currency):
            if forced_rate := self._context.get("forced_rate_from_register_payment"):
                return forced_rate
            if aml.move_id.payment_id:
                return aml.move_id.payment_id.foreign_inverse_rate
            if other_aml and not is_payment(aml) and is_payment(other_aml):
                return get_accounting_rate(other_aml, currency)
            if aml.move_id.is_invoice(include_receipts=True):
                exchange_rate_date = aml.move_id.invoice_date
            else:
                exchange_rate_date = aml._get_reconciliation_aml_field_value(
                    "date", shadowed_aml_values
                )
            return currency._get_conversion_rate(
                aml.company_currency_id, currency, aml.company_id, exchange_rate_date
            )

        def get_accounting_rate(aml, currency):
            if forced_rate := self._context.get("forced_rate_from_register_payment"):
                return forced_rate
            balance = aml._get_reconciliation_aml_field_value(
                "balance", shadowed_aml_values
            )
            amount_currency = aml._get_reconciliation_aml_field_value(
                "amount_currency", shadowed_aml_values
            )
            if not aml.company_currency_id.is_zero(balance) and not currency.is_zero(
                amount_currency
            ):
                return abs(amount_currency / balance)
            
            return 1.0
        

        aml = aml_values["aml"]
        other_aml = (other_aml_values or {}).get("aml")
        remaining_amount_curr = aml_values["amount_residual_currency"]
        remaining_amount = aml_values["amount_residual"]
        company_currency = aml.company_currency_id
        currency = aml._get_reconciliation_aml_field_value(
            "currency_id", shadowed_aml_values
        )
        account = aml._get_reconciliation_aml_field_value(
            "account_id", shadowed_aml_values
        )
        has_zero_residual = company_currency.is_zero(remaining_amount)
        has_zero_residual_currency = currency.is_zero(remaining_amount_curr)
        is_rec_pay_account = account.account_type in (
            "asset_receivable",
            "liability_payable",
        )

        available_residual_per_currency = {}

        if not has_zero_residual:
            available_residual_per_currency[company_currency] = {
                "residual": remaining_amount,
                "rate": 1,
            }
        if currency != company_currency and not has_zero_residual_currency:
            available_residual_per_currency[currency] = {
                "residual": remaining_amount_curr,
                "rate": get_accounting_rate(aml, currency),
            }

        if (
            currency == company_currency
            and is_rec_pay_account
            and not has_zero_residual
            and counterpart_currency != company_currency
        ):
            rate = get_odoo_rate(aml, other_aml, counterpart_currency)
            residual_in_foreign_curr = counterpart_currency.round(
                remaining_amount * rate
            )
            if not counterpart_currency.is_zero(residual_in_foreign_curr):
                available_residual_per_currency[counterpart_currency] = {
                    "residual": residual_in_foreign_curr,
                    "rate": rate,
                }
        elif (
            currency == counterpart_currency
            and currency != company_currency
            and not has_zero_residual_currency
        ):
            available_residual_per_currency[counterpart_currency] = {
                "residual": remaining_amount_curr,
                "rate": get_accounting_rate(aml, currency),
            }
        return available_residual_per_currency

    @api.onchange("quantity")
    def _onchange_quantity(self):
        if self.quantity < 0:
            raise ValidationError(_("The quantity entered cannot be negative"))

    @api.onchange("price_unit")
    def _onchange_price_unit(self):
        if self.price_unit < 0:
            raise ValidationError(_("The price entered cannot be negative"))
        self.foreign_price_manual = False
    
    
    @api.model
    def _prepare_reconciliation_single_partial(self, debit_values, credit_values, shadowed_aml_values=None):
        # 1. Llamada al método original
        res = super()._prepare_reconciliation_single_partial(
            debit_values, credit_values, shadowed_aml_values=shadowed_aml_values
        )

        if not res.get('partial_values'):
            return res

        partial_vals = res['partial_values']
        amount_company = partial_vals['amount']  # Monto conciliado en moneda base (Bs)

        def get_foreign_partial_amount(aml, amount_to_reconcile_bs):
            f_currency = aml.company_id.currency_foreign_id # Usar la de la compañía
            if not f_currency or aml.currency_id == f_currency:
                # Si la línea ya está en la moneda foránea, Odoo ya tiene amount_currency
                return abs(aml.amount_currency)
            
            # Si el balance en Bs es 0 (evitar división por cero)
            if not aml.balance:
                return 0.0

            # CALCULAMOS LA PROPORCIÓN
            # Si estoy conciliando 50 Bs de una factura de 100 Bs, 
            # debo conciliar el 50% del balance foráneo.
            total_bs = abs(aml.balance)
            total_foreign = abs(aml.foreign_balance)
            
            # Regla de 3: (Monto Conciliado Bs * Total Foráneo) / Total Bs
            ratio = amount_to_reconcile_bs / total_bs
            partial_foreign = total_foreign * ratio
            
            return f_currency.round(partial_foreign)

        debit_aml = debit_values['aml']
        credit_aml = credit_values['aml']

        # Calculamos cuánto aporta cada lado a la conciliación en moneda foránea
        foreign_debit_amount = get_foreign_partial_amount(debit_aml, amount_company)
        foreign_credit_amount = get_foreign_partial_amount(credit_aml, amount_company)

        # El monto de la conciliación parcial foránea es el mínimo de ambos lados proporcionalmente
        # pero usualmente en una conciliación parcial, el 'amount' de la partial es único.
        res['partial_values'].update({
            'foreign_amount': min(foreign_debit_amount, foreign_credit_amount),
            'debit_foreign_amount_currency': foreign_debit_amount,
            'credit_foreign_amount_currency': foreign_credit_amount,
        })

        return res
    

    @api.depends(
        'foreign_debit', 'foreign_credit','amount_residual',
        'foreign_balance', 'account_id',
        'matched_debit_ids',
        'matched_credit_ids',
        'matched_debit_ids.debit_foreign_amount_currency',
        'matched_credit_ids.credit_foreign_amount_currency',
    )
    def _compute_foreign_amount_residual(self):
        for line in self:
            if line.account_id.reconcile or line.account_id.account_type in ('asset_cash', 'liability_credit_card'):
                debit_foreign = sum(line.matched_debit_ids.mapped('debit_foreign_amount_currency'))
                credit_foreign = sum(line.matched_credit_ids.mapped('credit_foreign_amount_currency'))
                line.foreign_amount_residual = line.foreign_balance - credit_foreign + debit_foreign
                line.foreign_amount_residual_currency = line.foreign_amount_residual
            else:
                line.foreign_amount_residual = 0.0
                line.foreign_amount_residual_currency = 0.0

    @api.onchange('amount_currency', 'currency_id')
    def _inverse_amount_currency(self):
        for line in self:
            if line.currency_id == line.company_id.currency_id and line.balance != line.amount_currency:
                line.balance = line.amount_currency
            elif (
                line.currency_id != line.company_id.currency_id
                and not line.move_id.is_invoice(True)
                and not self.env.is_protected(self._fields['balance'], line)
            ):
                rate = line.currency_rate
                if not rate:
                    continue
                raw_balance = line.amount_currency / rate
                rounded_balance = line.company_id.currency_id.round(raw_balance)
                back_to_foreign = rounded_balance * rate
                diff_foreign = line.amount_currency - back_to_foreign
                if not float_is_zero(diff_foreign, precision_rounding=line.currency_id.rounding):
                    adjustment = float_round(diff_foreign / rate, precision_rounding=line.company_id.currency_id.rounding)
                    line.balance = rounded_balance + adjustment
                else:
                    line.balance = rounded_balance


    @api.depends('currency_rate', 'balance')
    def _compute_amount_currency(self):
        for line in self:
            if line.amount_currency is False:
                line.amount_currency = line.balance * line.currency_rate
            if line.currency_id == line.company_id.currency_id:
                line.amount_currency = line.balance

    @contextmanager
    def _sync_invoice(self, container):
        if container['records'].env.context.get('skip_invoice_line_sync'):
            yield
            return
        with super()._sync_invoice(container):
            yield
        self._apply_product_real_portion(container['records'])

    @api.model
    def _apply_product_real_portion(self, lines):
        """Correct cross-currency rounding on product lines.

        When an invoice is in a foreign currency, each product line's balance
        (company currency) is independently rounded to the company currency's
        precision. The sum of these rounded balances can differ by the currency
        rounding unit from the rounded conversion of the total line amount at
        the raw exchange rate. This method distributes that difference across
        product lines proportionally so the entry remains balanced.

        The expected total is computed via ``_convert`` (the raw rate from
        ``res.currency.rate``), not from ``line.currency_rate`` (which is
        derived from an already-rounded balance and amplifies the error).
        """
        for move in lines.move_id:
            if not move.is_invoice(include_receipts=True):
                continue
            if move.currency_id == move.company_currency_id:
                continue
            if move.state != 'draft':
                continue
            if move.env.cr.cache.get(('_real_portion_distributed', move.id)):
                continue

            cc = move.company_currency_id
            product_lines = lines.filtered(
                lambda l: l.move_id == move
                and l.display_type == 'product'
                and l.currency_id != l.company_currency_id
            )
            if not product_lines:
                continue

            total_currency = sum(product_lines.mapped('amount_currency'))
            rate_date = move.invoice_date or move.date or fields.Date.context_today(move)
            expected = cc.round(move.currency_id._convert(
                total_currency, cc, move.company_id, rate_date,
                custom_rate=move.foreign_inverse_rate or 0.0,
            ))
            actual = sum(product_lines.mapped('balance'))
            diff = cc.round(expected - actual)

            if cc.is_zero(diff):
                continue

            self._adjust_product_distribution(
                product_lines, diff, cc, move,
            )

    @api.model
    def _adjust_product_distribution(
        self, product_lines, diff, cc, move,
    ):
        bal_map = {line.id: line.balance for line in product_lines}
        total_abs = sum(abs(b) for b in bal_map.values())
        if cc.is_zero(total_abs):
            return

        sign = 1 if diff > 0 else -1
        abs_diff = abs(diff)
        sorted_ids = sorted(product_lines.ids, key=lambda lid: -abs(bal_map[lid]))
        remaining_units = round(abs_diff / cc.rounding)
        n = len(sorted_ids)

        for i, line_id in enumerate(sorted_ids):
            if remaining_units <= 0:
                break
            cur_bal = bal_map[line_id]
            if i < n - 1:
                ratio = abs(cur_bal) / total_abs
                share = cc.round(ratio * abs_diff)
                units = round(share / cc.rounding)
                if units > remaining_units:
                    units = remaining_units
            else:
                units = remaining_units
            new_balance = cc.round(cur_bal + sign * units * cc.rounding)
            product_lines.browse(line_id).balance = new_balance
            remaining_units -= units

        move.real_portion_count += 1