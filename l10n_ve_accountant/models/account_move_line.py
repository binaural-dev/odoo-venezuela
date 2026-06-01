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

    foreign_price = fields.Monetary(
        help="Foreign Price of the line",
        compute="_compute_foreign_price",
        currency_field="foreign_currency_id",
        store=True,
        readonly=False,
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
        compute="_compute_amount_residual",
        store=True,
        readonly=False,
    )
    foreign_amount_residual_currency = fields.Monetary(
        currency_field="foreign_currency_id",
        compute="_compute_amount_residual",
        store=True,
        readonly=False,
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
                line.foreign_price = line.price_unit * line.foreign_inverse_rate
            else:
                line.foreign_price = 0.0

    @api.depends('foreign_price', 'quantity', 'discount', 'price_subtotal', 'price_total')
    def _compute_foreign_subtotal(self):
        for move in self.mapped('move_id'):
            lines = self.filtered(lambda l: l.move_id == move and l.display_type not in ('line_section', 'line_note'))
            if not lines:
                continue

            total_foreign_subtotal_target = sum(l.foreign_price * l.quantity * (1 - l.discount / 100.0) for l in lines)
            
            accumulated_subtotal = 0.0
            accumulated_total = 0.0
            last_line = lines[-1]

            for line in lines:
                disc_factor = 1 - (line.discount / 100.0)
                
                if line != last_line:
                    line.foreign_subtotal = line.foreign_price * disc_factor * line.quantity
                    
                    ratio_iva = line.price_total / line.price_subtotal if line.price_subtotal else 1.0
                    line.foreign_price_total = line.foreign_subtotal * ratio_iva
                    
                    accumulated_subtotal += line.foreign_subtotal
                    accumulated_total += line.foreign_price_total
                else:
                   
                    line.foreign_subtotal = total_foreign_subtotal_target - accumulated_subtotal
                    
                    total_base_move = sum(l.price_total for l in lines)
                    subtotal_base_move = sum(l.price_subtotal for l in lines)
                    
                    global_ratio = total_base_move / subtotal_base_move if subtotal_base_move else 1.0
                    total_foreign_target = total_foreign_subtotal_target * global_ratio
                    
                    line.foreign_price_total = total_foreign_target - accumulated_total

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
            if line.move_id.journal_id == line.company_id.currency_exchange_journal_id:
                line.foreign_debit = 0.0
                line.foreign_credit = 0.0
                continue
            if line.not_foreign_recalculate:
                if line.foreign_debit_adjustment or line.foreign_credit_adjustment:
                    self._calculate_from_adjustment(line)
                continue

            if line.foreign_debit_adjustment or line.foreign_credit_adjustment:
                self._calculate_from_adjustment(line)

             
            elif line.display_type in ("line_section", "line_note"):
                self._calculate_zero(line)
            elif line.display_type in ("payment_term", "tax"):
                self._calculate_for_non_invoice(line)
            elif line.currency_id == line.company_id.currency_foreign_id and line.amount_currency:
                self._calculate_from_amount_currency(line)

            elif line.move_id.payment_id and "retention_foreign_amount" in self.env["account.payment"]._fields and line.move_id.payment_id.is_retention:
                self._calculate_from_retention(line)
            elif not line.move_id.is_invoice(include_receipts=True):
                self._calculate_for_non_invoice(line)
            elif line.display_type == "product":
                self._calculate_from_product(line)
            else:
                self._calculate_for_non_invoice(line)

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
                rate_date = line.date
                rate = foreign_currency._get_conversion_rate(
                    line.company_id.currency_id, 
                    foreign_currency,          
                    line.company_id,           
                    line.date           
                )

                inverse_rate_to_use = rate if inverse_rate_to_use == 0.0 else rate
     
        balance = sum(foreign_lines.mapped("amount_currency"))
        if balance and len(currency_lines) == 1:
            new_foreign_debit = abs(balance) if balance < 0 else 0.0
            new_foreign_credit = abs(balance) if balance > 0 else 0.0
        
        else:
            new_foreign_debit = line.debit * inverse_rate_to_use
            new_foreign_credit = line.credit * inverse_rate_to_use
        
       
        line.foreign_debit_no_format = line.debit * inverse_rate_to_use
        line.foreign_credit_no_format = line.credit * inverse_rate_to_use
        
        if new_foreign_debit:
            line.foreign_debit = new_foreign_debit
        if new_foreign_credit:
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
    

    @api.depends('debit', 'credit', 'amount_currency', 'account_id', 'currency_id', 'company_id',
                 'matched_debit_ids', 'matched_credit_ids','foreign_balance')
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
        amounts_map = {}
        foreign_amounts_map = {}

        if stored_lines:
            self.env['account.partial.reconcile'].flush_model()
            self.env['res.currency'].flush_model(['decimal_places'])

            aml_ids = tuple(stored_lines.ids)
            PartialModel = self.env['account.partial.reconcile']
            has_debit_fa = hasattr(PartialModel, 'debit_foreign_amount_currency')
            has_credit_fa = hasattr(PartialModel, 'credit_foreign_amount_currency')
            debit_field_sql = "SUM(part.debit_foreign_amount_currency)" if has_debit_fa else "0.0"
            credit_field_sql = "SUM(part.credit_foreign_amount_currency)" if has_credit_fa else "0.0"
            self._cr.execute(f'''
                SELECT
                    part.debit_move_id AS line_id,
                    'debit' AS flag,
                    COALESCE(SUM(part.amount), 0.0) AS amount,
                    SUM(part.debit_amount_currency) AS amount_currency,
                    COALESCE({debit_field_sql}, 0.0) AS foreign_amount
                FROM account_partial_reconcile part
                JOIN res_currency curr ON curr.id = part.debit_currency_id
                WHERE part.debit_move_id IN %s
                GROUP BY part.debit_move_id, curr.decimal_places
                UNION ALL
                SELECT
                    part.credit_move_id AS line_id,
                    'credit' AS flag,
                    COALESCE(SUM(part.amount), 0.0) AS amount,
                    SUM(part.credit_amount_currency) AS amount_currency,
                    COALESCE({credit_field_sql}, 0.0) AS foreign_amount
                FROM account_partial_reconcile part
                JOIN res_currency curr ON curr.id = part.credit_currency_id
                WHERE part.credit_move_id IN %s
                GROUP BY part.credit_move_id, curr.decimal_places
            ''', [aml_ids, aml_ids])
            for line_id, flag, amount, amount_currency, foreign_amount in self.env.cr.fetchall():
                amounts_map[(line_id, flag)] = (amount, amount_currency)
                foreign_amounts_map[(line_id, flag)] = foreign_amount
        else:
            amounts_map = {}

        # Lines that can't be reconciled with anything since the account doesn't allow that.
        for line in self - need_residual_lines:
            line.amount_residual = 0.0
            line.amount_residual_currency = 0.0
            line.foreign_amount_residual = 0.0
            line.foreign_amount_residual_currency = 0.0
            line.reconciled = False

        for line in need_residual_lines:
            # Since this part could be call on 'new' records, 'company_currency_id'/'currency_id' could be not set.
            comp_curr = line.company_currency_id or self.env.company.currency_id
            foreign_curr = line.currency_id or comp_curr

            # Retrieve the amounts in both foreign/company currencies. If the record is 'new', the amounts_map is empty.
            debit_amount, debit_amount_currency = amounts_map.get((line._origin.id, 'debit'), (0.0, 0.0))
            credit_amount, credit_amount_currency = amounts_map.get((line._origin.id, 'credit'), (0.0, 0.0))

            debit_foreign = foreign_amounts_map.get((line._origin.id, 'debit'), 0.0)
            credit_foreign = foreign_amounts_map.get((line._origin.id, 'credit'), 0.0)
            # Subtract the values from the account.partial.reconcile to compute the residual amounts.
            residual = line.balance - debit_amount + credit_amount
            residual_currency = line.amount_currency - debit_amount_currency + credit_amount_currency
            
            line.amount_residual = residual
            line.amount_residual_currency = residual_currency
            line.reconciled = (line.amount_residual == 0.0 and line.amount_residual_currency == 0.0)

            line.foreign_amount_residual = line.foreign_balance - debit_foreign + credit_foreign
            line.foreign_amount_residual_currency = line.foreign_amount_residual


    @api.onchange('amount_currency', 'currency_id','foreign_inverse_rate')
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


    @api.depends('currency_rate', 'balance')
    def _compute_amount_currency(self):
        for line in self:
            if line.amount_currency is False:
                line.amount_currency = line.balance * line.currency_rate
            if line.currency_id == line.company_id.currency_id:
                line.amount_currency = line.balance