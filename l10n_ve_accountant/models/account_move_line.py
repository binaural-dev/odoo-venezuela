import inspect
from odoo import api, fields, models, Command, _
from odoo.tools import float_compare
from odoo.exceptions import UserError, ValidationError
from odoo.tools import frozendict, formatLang, format_date, float_compare, Query
from datetime import date, timedelta
import traceback
from markupsafe import Markup

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
    )
    foreign_credit = fields.Monetary(
        currency_field="foreign_currency_id",
        compute="_compute_foreign_debit_credit",
        store=True,
    )
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

    

    @api.onchange("amount_currency", "currency_id")
    def _inverse_amount_currency(self):
        for line in self:

            if not line.currency_id:
                raise UserError(_("You must first select a currency"))
            
            if not line.foreign_currency_id:
                raise UserError(_("There is not a foreign currency defined"))
            
            if (
                line.currency_id == line.company_id.currency_id
                and line.balance != line.amount_currency
            ):
                line.balance = line.amount_currency
            elif (
                line.currency_id != line.company_id.currency_id
                and not line.move_id.is_invoice(True)
                and not self.env.is_protected(self._fields["balance"], line)
            ):
                rate = (
                    line.foreign_inverse_rate
                    if line.currency_id
                    in (self.env.ref("base.VEF"), self.env.ref("base.USD"))
                    else line.currency_rate
                )
                line.balance = line.company_id.currency_id.round(
                    line.amount_currency / rate
                )
            elif (
                line.currency_id != line.company_id.currency_id
                and not line.move_id.is_invoice(True)
                and line.move_id.payment_id
            ):
                if (
                    line.move_id.payment_id.foreign_inverse_rate != 0
                    and line.amount_currency != 0
                ):
                    line.balance = line.company_id.currency_id.round(
                        line.amount_currency
                        / line.move_id.payment_id.foreign_inverse_rate
                    )
                else:
                    raise UserError(_("The rate of foreingn currency should be greater than zero"))

 
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
                if line._origin.foreign_inverse_rate:
                    if line._origin.foreign_inverse_rate == line.foreign_inverse_rate:
                        continue
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
        "foreign_debit_adjustment",
        "foreign_credit_adjustment",
    )
    def _compute_foreign_debit_credit(self):
        for line in self:
            if line.not_foreign_recalculate:
                continue

            if line.foreign_debit_adjustment or line.foreign_credit_adjustment:
                self._calculate_from_adjustment(line)
            elif line.display_type in ("line_section", "line_note"):
                self._calculate_zero(line)
            elif line.display_type in ("payment_term", "tax"):
                self._calculate_from_balance(line)
            elif line.currency_id == line.company_id.currency_foreign_id and line.amount_currency:
                self._calculate_from_amount_currency(line)
            elif line.move_id.payment_id and "retention_foreign_amount" in self.env["account.payment"]._fields and line.move_id.payment_id.is_retention:
                self._calculate_from_retention(line)
            elif not line.move_id.is_invoice(include_receipts=True):
                self._calculate_for_non_invoice(line)
            elif line.display_type == "product":
                self._calculate_from_product(line)
            else:
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

        balance = sum(foreign_lines.mapped("amount_currency"))
        if balance and len(currency_lines) == 1:
            new_foreign_debit = abs(balance) if balance < 0 else 0.0
            new_foreign_credit = abs(balance) if balance > 0 else 0.0
        else:
            new_foreign_debit = line.debit * line.foreign_inverse_rate
            new_foreign_credit = line.credit * line.foreign_inverse_rate
        
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

    # @api.depends("foreign_rate", "balance")
    # def _compute_amount_currency(self):
    #     _logger.warning(
    #         "Source code: %s", inspect.getsource(super()_compute_amount_currency)
    #     )
    #     res = super()._compute_amount_currency()
    #     # for line in self:
    #     #     if line.amount_currency is False:
    #     #         line.amount_currency = line.currency_id.round(line.balance * line.currency_rate)
    #     #     if line.currency_id == line.company_id.currency_id:
    #     #         line.amount_currency = line.balance
    #     return res

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