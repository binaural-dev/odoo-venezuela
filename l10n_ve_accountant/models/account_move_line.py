import inspect
from odoo import api, fields, models, Command, _
from odoo.tools import float_compare
from odoo.exceptions import UserError, ValidationError
from odoo.tools import frozendict, formatLang, format_date, float_compare, Query, float_round

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

    foreign_price = fields.Float(
        help="Foreign Price of the line",
        compute="_compute_foreign_price",
        digits="Foreign Product Price",
        store=True,
        readonly=False,
    )
    foreign_subtotal = fields.Monetary(
        help="Foreign Subtotal of the line",
        compute="_compute_foreign_subtotal",
        currency_field="foreign_currency_id",
        digits="Foreign Product Price",
        store=True,
    )
    foreign_price_total = fields.Monetary(
        help="Foreign Total of the line",
        compute="_compute_foreign_subtotal",
        currency_field="foreign_currency_id",
        digits="Foreign Product Price",
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
        compute="_compute_foreign_amount_residuals",
        store=True,
        readonly=True,
    )
    foreign_amount_residual_currency = fields.Monetary(
        currency_field="foreign_currency_id",
        compute="_compute_foreign_amount_residuals",
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

    @api.depends("price_unit", "foreign_inverse_rate")
    def _compute_foreign_price(self):
        for line in self:
           
            if line.price_unit and line.foreign_inverse_rate:
                if line._origin.price_unit != line.price_unit or line.foreign_inverse_rate != line._origin.foreign_inverse_rate:
                   
                    line.foreign_price = line.price_unit * line.foreign_inverse_rate
            else:
                line.foreign_price = 0.0

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

    @api.depends(
        "debit",
        "credit",
        "foreign_subtotal",
        "foreign_balance",
        "amount_currency",
        "not_foreign_recalculate",
        "foreign_debit_adjustment",
        "foreign_credit_adjustment",
    )
    def _compute_foreign_debit_credit(self):
        for line in self:
            _logger.info("Computing foreign debit and credit for line %s", line.id)
            if line.not_foreign_recalculate:
                _logger.info("Skipping recalculation for line %s", line.id)
                if line.foreign_debit_adjustment or line.foreign_credit_adjustment:
                    self._calculate_from_adjustment(line)
                continue

            if line.foreign_debit_adjustment or line.foreign_credit_adjustment:
                _logger.info("Calculating from foreign_debit_adjustment or foreign_credit_adjustment")
                self._calculate_from_adjustment(line)

             
            elif line.display_type in ("line_section", "line_note"):
                self._calculate_zero(line)
            elif line.display_type in ("payment_term", "tax"):
                _logger.info("Calculating from payment_term or tax")
                self._calculate_from_balance(line)
            elif line.currency_id == line.company_id.currency_foreign_id and line.amount_currency:
                _logger.info("Calculating from amount_currency")
                self._calculate_from_amount_currency(line)

            elif line.move_id.payment_id and "retention_foreign_amount" in self.env["account.payment"]._fields and line.move_id.payment_id.is_retention:
                self._calculate_from_retention(line)
            elif not line.move_id.is_invoice(include_receipts=True):
                _logger.info("Calculating for non-invoice")
                self._calculate_for_non_invoice(line)
            elif line.display_type == "product":
                _logger.info("Calculating from product")
                self._calculate_from_product(line)
            else:
                _logger.info("Calculating from balance")
                self._calculate_from_balance(line)

    def _calculate_from_adjustment(self, line):
        new_foreign_debit = abs(line.foreign_debit_adjustment) if line.foreign_debit_adjustment else 0.0
        if line.foreign_debit != new_foreign_debit:

            line.foreign_debit = new_foreign_debit

        new_foreign_credit = abs(line.foreign_credit_adjustment) if line.foreign_credit_adjustment else 0.0

        if line.foreign_credit != new_foreign_credit:

            line.foreign_credit = new_foreign_credit         

    def _calculate_zero(self, line):
        """Asigna cero para secciones o notas."""
        if line.foreign_debit != 0.0:
            line.foreign_debit = 0.0
        if line.foreign_credit != 0.0:
            line.foreign_credit = 0.0

    def _calculate_from_balance(self, line):
        new_foreign_debit = abs(line.foreign_balance) if line.foreign_balance > 0 else 0.0
        if line.foreign_debit != new_foreign_debit:
            line.foreign_debit = new_foreign_debit

        new_foreign_credit = abs(line.foreign_balance) if line.foreign_balance < 0 else 0.0
        if line.foreign_credit != new_foreign_credit:
            line.foreign_credit = new_foreign_credit

    def _calculate_from_amount_currency(self, line):
        new_foreign_debit = abs(line.amount_currency) if line.amount_currency > 0 else 0.0
        if line.foreign_debit != new_foreign_debit:
            line.foreign_debit = new_foreign_debit

        new_foreign_credit = abs(line.amount_currency) if line.amount_currency < 0 else 0.0
        if line.foreign_credit != new_foreign_credit:
            line.foreign_credit = new_foreign_credit

    def _calculate_from_retention(self, line):
        retention_amount = line.move_id.payment_id.retention_foreign_amount
        new_foreign_debit = 0.0
        new_foreign_credit = 0.0
        if not line.currency_id.is_zero(line.debit):
            new_foreign_debit = retention_amount
        elif not line.currency_id.is_zero(line.credit):
            new_foreign_credit = retention_amount

        if line.foreign_debit != new_foreign_debit:
            line.foreign_debit = new_foreign_debit
        if line.foreign_credit != new_foreign_credit:
            line.foreign_credit = new_foreign_credit

    def _calculate_for_non_invoice(self, line):
        
        foreign_lines = line.move_id.line_ids.filtered(
            lambda l: l.currency_id == l.company_id.currency_foreign_id
        )
        currency_lines = line.move_id.line_ids.filtered(
            lambda l: l.currency_id == l.company_id.currency_id
        )
        new_foreign_debit = 0.0
        new_foreign_credit = 0.0

        rate_is_zero = line.foreign_inverse_rate == 0.0
        is_base_currency = line.currency_id == line.company_id.currency_id
        
        inverse_rate_to_use = line.foreign_inverse_rate
        
        if is_base_currency and rate_is_zero:
            foreign_currency = line.company_id.currency_foreign_id
            
           
            if foreign_currency:
                rate = foreign_currency._get_conversion_rate(
                    line.company_id.currency_id, 
                    foreign_currency,          
                    line.company_id,           
                    line.move_id.origin_payment_advanced_payment_id.date if line.move_id.origin_payment_advanced_payment_id else line.date #asientos de cruce toman tasa del pago          
                )

                inverse_rate_to_use = rate if inverse_rate_to_use <= 0.0 else rate
     
        balance = sum(foreign_lines.mapped("amount_currency"))
        if balance and len(currency_lines) == 1:
            new_foreign_debit = abs(balance) if balance < 0 else 0.0
            new_foreign_credit = abs(balance) if balance > 0 else 0.0
        
        else:
            new_foreign_debit = line.debit * inverse_rate_to_use
            new_foreign_credit = line.credit * inverse_rate_to_use
        
       
        line.foreign_debit_no_format = line.debit * inverse_rate_to_use
        line.foreign_credit_no_format = line.credit * inverse_rate_to_use
        
        if line.foreign_debit != new_foreign_debit:
            line.foreign_debit = new_foreign_debit
        if line.foreign_credit != new_foreign_credit:
            line.foreign_credit = new_foreign_credit

    def _calculate_from_product(self, line):
        
        sign = line.move_id.direction_sign * -1
        amount = line.foreign_subtotal * sign
        new_foreign_debit = abs(amount) if amount < 0 else 0.0
        if line.foreign_debit != new_foreign_debit:
            line.foreign_debit = new_foreign_debit

        new_foreign_credit = abs(amount) if amount > 0 else 0.0
        if line.foreign_credit != new_foreign_credit:
            line.foreign_credit = new_foreign_credit
        
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
            if other_aml and not is_payment(aml) and is_payment(other_aml):
                # >>>> Integra
                if aml.move_id.payment_id:
                    return aml.move_id.payment_id.foreign_inverse_rate
                # <<<< Integra
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

    @api.model
    def abs_amount_lines_ids_adjust(self):
        for line in self:
            line.write(
                {
                    "foreign_debit_adjustment": abs(line.foreign_debit_adjustment),
                    "foreign_credit_adjustment": abs(line.foreign_credit_adjustment),
                    "foreign_debit": abs(line.foreign_debit),
                    "foreign_credit": abs(line.foreign_credit),
                }
            )

    @api.depends(
        "foreign_inverse_rate",
        "foreign_currency_id",
        "foreign_rate",
        "foreign_price",
    )
    def _compute_all_tax(self):
        res = super(AccountMoveLine, self)._compute_all_tax()
        for line in self:
            sign = line.move_id.direction_sign

            if line.display_type == "product" and line.move_id.is_invoice(True):
                amount_currency = sign * line.foreign_price * (1 - line.discount / 100)
                handle_price_include = True
                quantity = line.quantity
            else:
                amount_currency = (
                    line.amount_currency * line.move_id.foreign_inverse_rate
                )
                handle_price_include = False
                quantity = 1

            compute_all_currency = line.tax_ids.compute_all(
                amount_currency,
                currency=line.foreign_currency_id,
                quantity=quantity,
                product=line.product_id,
                partner=line.move_id.partner_id or line.partner_id,
                is_refund=line.is_refund,
                handle_price_include=handle_price_include,
                include_caba_tags=line.move_id.always_tax_exigible,
                fixed_multiplicator=sign,
            )

            for tax in compute_all_currency["taxes"]:
                for key in list(line.compute_all_tax.keys()):
                    if not key.get("tax_repartition_line_id", False):
                        continue

                    if tax["tax_repartition_line_id"] == key["tax_repartition_line_id"]:
                        line.compute_all_tax[key]["foreign_balance"] = tax["amount"]
        return res

    @api.onchange("quantity")
    def _onchange_quantity(self):
        if self.quantity < 0:
            raise ValidationError(_("The quantity entered cannot be negative"))

    @api.onchange("price_unit")
    def _onchange_price_unit(self):
        if self.price_unit < 0:
            raise ValidationError(_("The price entered cannot be negative"))
        

    def write(self, vals):
        old_values = {
            line.id: {
                'foreign_debit': line.foreign_debit,
                'foreign_credit': line.foreign_credit
            } for line in self
        }
    
        res = super(AccountMoveLine, self).write(vals)

        for line in self:
            old_line_data = old_values.get(line.id)
            if old_line_data:
                old_debit = old_line_data['foreign_debit']
                new_debit = line.foreign_debit
                old_credit = old_line_data['foreign_credit']
                new_credit = line.foreign_credit

                if old_debit != new_debit or old_credit != new_credit:
                    if line.id and line.move_id and line.move_id.id:
                        message_parts = []
                        
                        message_parts.append(_("<b>The accounting line has been updated:</b>"))
                        
                        message_parts.append(_("<b>Account:</b> %s") % line.account_id.display_name)
                        
                        if old_debit != new_debit:
                            message_parts.append(_("<b>Foreign Debit Amount:</b> from %s to %s") % (str(old_debit).replace('.', ','), str(new_debit).replace('.', ',')))
                        if old_credit != new_credit:
                            message_parts.append(_("<b>Foreign Credit Amount:</b> from %s to %s") % (str(old_credit).replace('.', ','), str(new_credit).replace('.', ',')))

                        msg_body = "<br/>".join(message_parts)
                        
                        final_body = Markup(msg_body)

                        self.env['mail.message'].create({
                            'body': final_body,
                            'model': line.move_id._name,
                            'res_id': line.move_id.id,
                            'message_type': 'comment',
                            'subtype_id': self.env.ref('mail.mt_note').id,
                            'author_id': self.env.user.partner_id.id,
                        })

        return res

    def _get_manual_foreign_amount_residual(
        self,
        currency=None,
        foreign_debit=None,
        foreign_credit=None,
        partials=None,
    ):
        """
        Calculates the manual residual amount in foreign currency for the move line.
        Considers matched partials and computes the remaining amount after reconciliation.
        Returns a tuple: (rounded residual, manual_available).
        """
        self.ensure_one()

        currency = currency or self.foreign_currency_id
        if not currency:
            return 0.0, False

        if self.foreign_currency_id and currency != self.foreign_currency_id:
            return 0.0, False

        foreign_debit = foreign_debit if foreign_debit is not None else self.foreign_debit
        foreign_credit = (
            foreign_credit if foreign_credit is not None else self.foreign_credit
        )

        manual_total = (foreign_debit or 0.0) - (foreign_credit or 0.0)

        partials = partials or (self.matched_debit_ids | self.matched_credit_ids)
        manual_partial_total = 0.0
        for partial in partials:
            amount = 0.0
            partial_currency = False
            if partial.debit_move_id == self:
                amount = partial.debit_amount_currency or 0.0
                partial_currency = partial.debit_currency_id
            elif partial.credit_move_id == self:
                amount = partial.credit_amount_currency or 0.0
                partial_currency = partial.credit_currency_id

            if partial_currency == currency and amount:
                manual_partial_total += amount

        if currency.is_zero(manual_total) and currency.is_zero(manual_partial_total):
            return 0.0, False

        if currency.is_zero(manual_total):
            balance_sign = 1 if self.balance >= 0 else -1
        else:
            balance_sign = 1 if manual_total >= 0 else -1

        residual = manual_total - balance_sign * manual_partial_total
        if balance_sign > 0:
            residual = max(residual, 0.0)
        else:
            residual = min(residual, 0.0)

        return residual, True

    @api.depends(
        "foreign_currency_id",
        "foreign_debit",
        "foreign_credit",
        "matched_debit_ids.debit_amount_currency",
        "matched_debit_ids.debit_currency_id",
        "matched_credit_ids.credit_amount_currency",
        "matched_credit_ids.credit_currency_id",
    )
    def _compute_foreign_amount_residuals(self):
        """
        Computes and stores the foreign currency residuals for each move line.
        Uses _get_manual_foreign_amount_residual for calculation.
        """
        for line in self:
            residual, manual_available = line._get_manual_foreign_amount_residual()
            line.foreign_amount_residual = residual if manual_available else 0.0
            line.foreign_amount_residual_currency = residual if manual_available else 0.0

    def _prepare_reconciliation_single_partial(
        self,
        debit_vals,
        credit_vals,
        shadowed_aml_values=None,
        **kwargs,
    ):
        """
        Prepares the values for a single partial reconciliation between debit and credit lines.
        Calculates foreign currency progress and updates partial values accordingly.
        Returns the result from the super method with updated foreign currency fields.
        """
        debit_line = debit_vals.get("aml")
        credit_line = credit_vals.get("aml")

        initial_debit_amount_residual = debit_vals.get("amount_residual")
        if initial_debit_amount_residual is None and debit_line:
            initial_debit_amount_residual = getattr(
                debit_line, "amount_residual", 0.0
            )
        initial_credit_amount_residual = credit_vals.get("amount_residual")
        if initial_credit_amount_residual is None and credit_line:
            initial_credit_amount_residual = getattr(
                credit_line, "amount_residual", 0.0
            )

        initial_debit_foreign_residual = debit_vals.get("foreign_amount_residual")
        if initial_debit_foreign_residual is None and debit_line:
            initial_debit_foreign_residual = getattr(
                debit_line, "foreign_amount_residual", 0.0
            )
        initial_debit_foreign_residual_currency = debit_vals.get(
            "foreign_amount_residual_currency"
        )
        if initial_debit_foreign_residual_currency is None and debit_line:
            initial_debit_foreign_residual_currency = getattr(
                debit_line, "foreign_amount_residual_currency", 0.0
            )

        initial_credit_foreign_residual = credit_vals.get("foreign_amount_residual")
        if initial_credit_foreign_residual is None and credit_line:
            initial_credit_foreign_residual = getattr(
                credit_line, "foreign_amount_residual", 0.0
            )
        initial_credit_foreign_residual_currency = credit_vals.get(
            "foreign_amount_residual_currency"
        )
        if initial_credit_foreign_residual_currency is None and credit_line:
            initial_credit_foreign_residual_currency = getattr(
                credit_line, "foreign_amount_residual_currency", 0.0
            )

        res = super()._prepare_reconciliation_single_partial(
            debit_vals,
            credit_vals,
            shadowed_aml_values=shadowed_aml_values,
            **kwargs,
        )

        partial_vals = res.get("partial_values")
        if not partial_vals:
            return res

        new_debit_amount_residual = debit_vals.get("amount_residual")
        new_credit_amount_residual = credit_vals.get("amount_residual")

        def _compute_foreign_progress(
            line,
            initial_company_residual,
            new_company_residual,
            initial_foreign_residual,
            initial_foreign_residual_currency,
        ):
            if not line or not line.foreign_currency_id:
                return 0.0, abs(initial_foreign_residual or 0.0), 0.0, abs(
                    initial_foreign_residual_currency or 0.0
                )

            company_foreign_currency = line.company_id.currency_foreign_id
            foreign_currency = line.foreign_currency_id

            initial_company = abs(initial_company_residual or 0.0)
            new_company = abs(new_company_residual or 0.0)
            line_foreign_total = 0.0
            # For credit line, use foreign_credit directly for currency calculation
            if line and line.foreign_credit is not None:
                line_foreign_total = abs(line.foreign_credit)
            elif line and line.foreign_debit is not None:
                line_foreign_total = abs(line.foreign_debit)
            initial_foreign = line_foreign_total or abs(initial_foreign_residual or 0.0)
            if initial_foreign_residual_currency is not None:
                initial_foreign_currency = abs(initial_foreign_residual_currency)
            else:
                initial_foreign_currency = initial_foreign

            if line_foreign_total:
                initial_foreign_currency = line_foreign_total

            if not initial_company:
                return (
                    0.0,
                    initial_foreign,
                    0.0,
                    initial_foreign_currency,
                )

            matched_ratio = min(
                max((initial_company - new_company) / initial_company, 0.0),
                1.0,
            )

            partial_foreign_currency = foreign_currency.round(
                initial_foreign_currency * matched_ratio
            )
            new_foreign_currency = foreign_currency.round(
                max(initial_foreign_currency - partial_foreign_currency, 0.0)
            )

            rounding_currency = company_foreign_currency or foreign_currency
            partial_foreign = rounding_currency.round(initial_foreign * matched_ratio)
            new_foreign = rounding_currency.round(
                max(initial_foreign - partial_foreign, 0.0)
            )

            return (
                partial_foreign,
                new_foreign,
                partial_foreign_currency,
                new_foreign_currency,
            )

        (
            debit_foreign_amount,
            debit_foreign_residual,
            debit_foreign_amount_currency,
            debit_foreign_residual_currency,
        ) = _compute_foreign_progress(
            debit_line,
            initial_debit_amount_residual,
            new_debit_amount_residual,
            initial_debit_foreign_residual,
            initial_debit_foreign_residual_currency,
        )

        (
            credit_foreign_amount,
            credit_foreign_residual,
            credit_foreign_amount_currency,
            credit_foreign_residual_currency,
        ) = _compute_foreign_progress(
            credit_line,
            initial_credit_amount_residual,
            new_credit_amount_residual,
            initial_credit_foreign_residual,
            initial_credit_foreign_residual_currency,
        )

        company_foreign_currency = False
        line_for_company = debit_line or credit_line
        if line_for_company:
            company_foreign_currency = line_for_company.company_id.currency_foreign_id

        preferred_candidates = []
        if company_foreign_currency:
            if (
                debit_line
                and debit_line.foreign_currency_id == company_foreign_currency
                and debit_foreign_amount_currency
            ):
                preferred_candidates.append(debit_foreign_amount_currency)
            if (
                credit_line
                and credit_line.foreign_currency_id == company_foreign_currency
                and credit_foreign_amount_currency
            ):
                preferred_candidates.append(credit_foreign_amount_currency)

        partial_foreign_amount = 0.0
        partial_foreign_amount = partial_vals.get("amount") *line_for_company.foreign_inverse_rate if company_foreign_currency == self.env.ref("base.VEF") else partial_vals.get("amount") / line_for_company.foreign_inverse_rate

        partial_vals.update(
            {
                "foreign_amount": partial_foreign_amount,
                "debit_foreign_amount_currency": debit_foreign_amount_currency,
                "credit_foreign_amount_currency": credit_foreign_amount_currency,
            }
        )

        if debit_line and debit_line.foreign_currency_id:
            debit_vals["foreign_amount_residual"] = debit_foreign_residual
            debit_vals["foreign_amount_residual_currency"] = (
                debit_foreign_residual_currency
            )

        if credit_line and credit_line.foreign_currency_id:
            credit_vals["foreign_amount_residual"] = credit_foreign_residual
            credit_vals["foreign_amount_residual_currency"] = (
                credit_foreign_residual_currency
            )
        return res
    

    @api.depends('debit', 'credit', 'amount_currency', 'account_id', 'currency_id', 'company_id',
                 'matched_debit_ids', 'matched_credit_ids')
    def _compute_amount_residual(self):
        """ Computes the residual amount of a move line from a reconcilable account in the company currency and the line's currency.
            This amount will be 0 for fully reconciled lines or lines from a non-reconcilable account, the original line amount
            for unreconciled lines, and something in-between for partially reconciled lines.
        """
        need_residual_lines = self.filtered(lambda x: x.account_id.reconcile or x.account_id.account_type in ('asset_cash', 'liability_credit_card'))
        # Run the residual amount computation on all lines stored in the db. By
        # using _origin, new records (with a NewId) are excluded and the
        # computation works automagically for virtual onchange records as well.
        stored_lines = need_residual_lines._origin

        if stored_lines:
            self.env['account.partial.reconcile'].flush_model()
            self.env['res.currency'].flush_model(['decimal_places'])

            aml_ids = tuple(stored_lines.ids)
            self._cr.execute('''
                SELECT
                    part.debit_move_id AS line_id,
                    'debit' AS flag,
                    COALESCE(SUM(part.amount), 0.0) AS amount,
                    SUM(part.debit_amount_currency) AS amount_currency
                FROM account_partial_reconcile part
                JOIN res_currency curr ON curr.id = part.debit_currency_id
                WHERE part.debit_move_id IN %s
                GROUP BY part.debit_move_id, curr.decimal_places
                UNION ALL
                SELECT
                    part.credit_move_id AS line_id,
                    'credit' AS flag,
                    COALESCE(SUM(part.amount), 0.0) AS amount,
                    SUM(part.credit_amount_currency) AS amount_currency
                FROM account_partial_reconcile part
                JOIN res_currency curr ON curr.id = part.credit_currency_id
                WHERE part.credit_move_id IN %s
                GROUP BY part.credit_move_id, curr.decimal_places
            ''', [aml_ids, aml_ids])
            amounts_map = {
                (line_id, flag): (amount, amount_currency)
                for line_id, flag, amount, amount_currency in self.env.cr.fetchall()
            }
        else:
            amounts_map = {}

        # Lines that can't be reconciled with anything since the account doesn't allow that.
        for line in self - need_residual_lines:
            line.amount_residual = 0.0
            line.amount_residual_currency = 0.0
            line.reconciled = False

        for line in need_residual_lines:
            # Since this part could be call on 'new' records, 'company_currency_id'/'currency_id' could be not set.
            comp_curr = line.company_currency_id or self.env.company.currency_id
            foreign_curr = line.currency_id or comp_curr

            # Retrieve the amounts in both foreign/company currencies. If the record is 'new', the amounts_map is empty.
            debit_amount, debit_amount_currency = amounts_map.get((line._origin.id, 'debit'), (0.0, 0.0))
            credit_amount, credit_amount_currency = amounts_map.get((line._origin.id, 'credit'), (0.0, 0.0))

            # Subtract the values from the account.partial.reconcile to compute the residual amounts.
            residual = line.balance - debit_amount + credit_amount
            residual_currency = line.amount_currency - debit_amount_currency + credit_amount_currency
            
            line.amount_residual = comp_curr.round(residual)
            line.amount_residual_currency = foreign_curr.round(residual_currency)
            # Para determinar si está conciliado, usamos una tolerancia mínima 
            # en lugar de un cero absoluto, o comparamos directamente.
            line.reconciled = (line.amount_residual == 0.0 and line.amount_residual_currency == 0.0)


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
                line.balance = line.amount_currency / line.currency_rate
