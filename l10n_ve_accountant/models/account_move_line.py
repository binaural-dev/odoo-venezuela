from odoo import api, fields, models, Command, _
from odoo.tools import float_compare
from odoo.exceptions import UserError
from odoo.tools import frozendict, formatLang, format_date, float_compare, Query
from datetime import date, timedelta
import traceback

import logging

_logger = logging.getLogger(__name__)


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    not_foreign_recalculate = fields.Boolean()
    foreign_currency_id = fields.Many2one(related="move_id.foreign_currency_id", store=True)
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
        currency_field="foreign_currency_id", compute="_compute_foreign_debit_credit", store=True
    )
    foreign_credit = fields.Monetary(
        currency_field="foreign_currency_id", compute="_compute_foreign_debit_credit", store=True
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
                    if line.currency_id in (self.env.ref("base.VEF"), self.env.ref("base.USD"))
                    else line.currency_rate
                )
                line.balance = line.company_id.currency_id.round(line.amount_currency / rate)
            elif (
                line.currency_id != line.company_id.currency_id
                and not line.move_id.is_invoice(True)
                and line.move_id.payment_id
            ):
                if line.move_id.payment_id.foreign_inverse_rate != 0 and line.amount_currency != 0:
                    line.balance = line.company_id.currency_id.round(
                        line.amount_currency / line.move_id.payment_id.foreign_inverse_rate
                    )
                else:
                    raise UserError(_("The rate should be greater than zero"))

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
            line.foreign_price = line.price_unit * line.foreign_inverse_rate

    @api.depends("foreign_price", "quantity", "discount", "tax_ids", "price_unit")
    def _compute_foreign_subtotal(self):
        for line in self:
            line_discount_price_unit = line.foreign_price * (1 - (line.discount / 100.0))
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

            if line.display_type in ("payment_term", "tax"):
                line.foreign_debit = abs(line.foreign_balance) if line.foreign_balance > 0 else 0.0
                line.foreign_credit = abs(line.foreign_balance) if line.foreign_balance < 0 else 0.0
                # 1 Case: Payment Term
                # In this case, we don't want to calculate the foreign debit and credit
                continue

            if line.display_type in ("line_section", "line_note"):
                line.foreign_debit = line.foreign_credit = 0.0
                # 2 Case: not Product
                # In this case, we don't want to calculate the foreign debit and credit
                continue

            if line.foreign_debit_adjustment:
                line.foreign_debit = abs(line.foreign_debit_adjustment)
                # 3 Case: Foreign Debit Adjustment
                # In this case, we need to set the foreign debit manually
                continue

            if line.foreign_credit_adjustment:
                line.foreign_credit = abs(line.foreign_credit_adjustment)
                # 4 Case: Foreign Credit Adjustment
                # In this case, we need to set the foreign credit manually
                continue

            if line.currency_id == line.company_id.currency_foreign_id and line.amount_currency:
                line.foreign_debit = abs(line.amount_currency) if line.amount_currency > 0 else 0.0
                line.foreign_credit = abs(line.amount_currency) if line.amount_currency < 0 else 0.0
                continue

            if (
                line.move_id.payment_id
                and "retention_foreign_amount" in self.env["account.payment"]._fields
                and line.move_id.payment_id.is_retention
            ):
                # 5 Case: Retention
                # In this case, we need to set the foreign debit and credit of the retention
                if not line.currency_id.is_zero(line.debit):
                    line.foreign_debit = line.move_id.payment_id.retention_foreign_amount
                    continue
                if not line.currency_id.is_zero(line.credit):
                    line.foreign_credit = line.move_id.payment_id.retention_foreign_amount
                    continue

            if not line.move_id.is_invoice(include_receipts=True):
                # 6 Case: Not Invoice
                # In this case, we need to calculate the foreign debit and credit with rate
                foreign_lines = line.move_id.line_ids.filtered(
                    lambda l: l.currency_id == l.company_id.currency_foreign_id
                )
                currency_lines = line.move_id.line_ids.filtered(
                    lambda l: l.currency_id == l.company_id.currency_id
                )

                balance = sum((foreign_lines).mapped("amount_currency"))
                if balance and len(currency_lines) == 1:
                    line.foreign_debit = abs(balance) if balance < 0 else 0.0
                    line.foreign_credit = abs(balance) if balance > 0 else 0.0
                    continue

                line.foreign_debit = line.debit * line.foreign_inverse_rate
                line.foreign_credit = line.credit * line.foreign_inverse_rate
                continue

            if line.display_type == "product":
                # 7 Case: Product
                # In this case, we need to calculate the foreign debit and credit with subtotal
                sign = line.move_id.direction_sign * -1
                amount = line.foreign_subtotal * sign
                line.foreign_debit = abs(amount) if amount < 0 else 0.0
                line.foreign_credit = abs(amount) if amount > 0 else 0.0
                continue

            line.foreign_debit = abs(line.foreign_balance) if line.foreign_balance < 0 else 0.0
            line.foreign_credit = abs(line.foreign_balance) if line.foreign_balance > 0 else 0.0

    @api.depends("foreign_credit", "foreign_debit")
    def _compute_foreign_balance(self):
        for line in self:
            line.foreign_balance = line.foreign_debit - line.foreign_credit

    def _inverse_foreign_balance(self):
        for line in self:
            line.foreign_debit = abs(line.foreign_balance) if line.foreign_balance > 0 else 0.0
            line.foreign_credit = abs(line.foreign_balance) if line.foreign_balance < 0 else 0.0

    @api.depends("foreign_rate", "balance")
    def _compute_amount_currency(self):
        for line in self:
            if line.amount_currency is False:
                line.amount_currency = line.currency_id.round(line.balance * line.foreign_rate)
            if line.currency_id == line.company_id.currency_id:
                line.amount_currency = line.balance

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
        distribution_plan = distribution_on_each_plan.get(account.root_plan_id, 0) + distribution
        decimal_precision = self.env["decimal.precision"].precision_get("Percentage Analytic")
        if float_compare(distribution_plan, 100, precision_digits=decimal_precision) == 0:
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
    def _prepare_reconciliation_single_partial(self, debit_vals, credit_vals):
        """
        DEV:
        This function was overridden in order to get the pay rate and put it in the
        difference calculation.

        Originally it uses the rate of the date of the entry line, so it generates
        a difference and does not allow to fully reconcile

        ODOO:
        Prepare the values to create an account.partial.reconcile later when reconciling the dictionaries passed
        as parameters, each one representing an account.move.line.
        :param debit_vals:  The values of account.move.line to consider for a debit line.
        :param credit_vals: The values of account.move.line to consider for a credit line.
        :return:            A dictionary:
            * debit_vals:   None if the line has nothing left to reconcile.
            * credit_vals:  None if the line has nothing left to reconcile.
            * partial_vals: The newly computed values for the partial.
        """

        def get_odoo_rate(vals):
            if vals.get("record") and vals["record"].move_id.is_invoice(include_receipts=True):
                exchange_rate_date = vals["record"].move_id.invoice_date
            else:
                exchange_rate_date = vals["date"]
            return recon_currency._get_conversion_rate(
                company_currency, recon_currency, vals["company"], exchange_rate_date
            )

        def get_accounting_rate(vals):
            if company_currency.is_zero(vals["balance"]) or vals["currency"].is_zero(
                vals["amount_currency"]
            ):
                return None
            else:
                return abs(vals["amount_currency"]) / abs(vals["balance"])

        # ==== Determine the currency in which the reconciliation will be done ====
        # In this part, we retrieve the residual amounts, check if they are zero or not and determine in which
        # currency and at which rate the reconciliation will be done.

        res = {
            "debit_vals": debit_vals,
            "credit_vals": credit_vals,
        }
        remaining_debit_amount_curr = debit_vals["amount_residual_currency"]
        remaining_credit_amount_curr = credit_vals["amount_residual_currency"]
        remaining_debit_amount = debit_vals["amount_residual"]
        remaining_credit_amount = credit_vals["amount_residual"]

        company_currency = debit_vals["company"].currency_id
        has_debit_zero_residual = company_currency.is_zero(remaining_debit_amount)
        has_credit_zero_residual = company_currency.is_zero(remaining_credit_amount)
        has_debit_zero_residual_currency = debit_vals["currency"].is_zero(
            remaining_debit_amount_curr
        )
        has_credit_zero_residual_currency = credit_vals["currency"].is_zero(
            remaining_credit_amount_curr
        )
        is_rec_pay_account = debit_vals.get("record") and debit_vals["record"].account_type in (
            "asset_receivable",
            "liability_payable",
        )

        if (
            debit_vals["currency"] == credit_vals["currency"] == company_currency
            and not has_debit_zero_residual
            and not has_credit_zero_residual
        ):
            # Everything is expressed in company's currency and there is something left to reconcile.
            recon_currency = company_currency
            debit_rate = credit_rate = 1.0
            recon_debit_amount = remaining_debit_amount
            recon_credit_amount = -remaining_credit_amount
        elif (
            debit_vals["currency"] == company_currency
            and is_rec_pay_account
            and not has_debit_zero_residual
            and credit_vals["currency"] != company_currency
            and not has_credit_zero_residual_currency
        ):
            # The credit line is using a foreign currency but not the opposite line.
            # In that case, convert the amount in company currency to the foreign currency one.

            recon_currency = credit_vals["currency"]
            debit_rate = get_odoo_rate(debit_vals)
            credit_rate = get_accounting_rate(credit_vals)
            # --------------------------------------
            # BINAURAL
            # --------------------------------------
            if credit_vals["record"].move_id.payment_id:
                debit_rate = credit_vals["record"].move_id.payment_id.foreign_inverse_rate
                credit_rate = credit_vals["record"].move_id.payment_id.foreign_inverse_rate
            # --------------------------------------

            recon_debit_amount = recon_currency.round(remaining_debit_amount * debit_rate)
            recon_credit_amount = -remaining_credit_amount_curr
        elif (
            debit_vals["currency"] != company_currency
            and is_rec_pay_account
            and not has_debit_zero_residual_currency
            and credit_vals["currency"] == company_currency
            and not has_credit_zero_residual
        ):
            # The debit line is using a foreign currency but not the opposite line.
            # In that case, convert the amount in company currency to the foreign currency one.
            recon_currency = debit_vals["currency"]
            debit_rate = get_accounting_rate(debit_vals)
            credit_rate = get_odoo_rate(credit_vals)

            # --------------------------------------
            # BINAURAL
            # --------------------------------------
            if debit_vals["record"].move_id.payment_id:
                credit_rate = debit_vals["record"].move_id.payment_id.foreign_inverse_rate
                debit_rate = debit_vals["record"].move_id.payment_id.foreign_inverse_rate
            # --------------------------------------

            recon_debit_amount = remaining_debit_amount_curr
            recon_credit_amount = recon_currency.round(-remaining_credit_amount * credit_rate)
        elif (
            debit_vals["currency"] == credit_vals["currency"]
            and debit_vals["currency"] != company_currency
            and not has_debit_zero_residual_currency
            and not has_credit_zero_residual_currency
        ):
            # Both lines are sharing the same foreign currency.
            recon_currency = debit_vals["currency"]
            debit_rate = get_accounting_rate(debit_vals)
            credit_rate = get_accounting_rate(credit_vals)
            recon_debit_amount = remaining_debit_amount_curr
            recon_credit_amount = -remaining_credit_amount_curr
        elif (
            debit_vals["currency"] == credit_vals["currency"]
            and debit_vals["currency"] != company_currency
            and (has_debit_zero_residual_currency or has_credit_zero_residual_currency)
        ):
            # Special case for exchange difference lines. In that case, both lines are sharing the same foreign
            # currency but at least one has no amount in foreign currency.
            # In that case, we don't want a rate for the opposite line because the exchange difference is supposed
            # to reduce only the amount in company currency but not the foreign one.
            recon_currency = company_currency
            debit_rate = None
            credit_rate = None
            recon_debit_amount = remaining_debit_amount
            recon_credit_amount = -remaining_credit_amount
        else:
            # Multiple involved foreign currencies. The reconciliation is done using the currency of the company.
            recon_currency = company_currency
            debit_rate = get_accounting_rate(debit_vals)
            credit_rate = get_accounting_rate(credit_vals)
            recon_debit_amount = remaining_debit_amount
            recon_credit_amount = -remaining_credit_amount

        # Check if there is something left to reconcile. Move to the next loop iteration if not.
        skip_reconciliation = False
        if recon_currency.is_zero(recon_debit_amount):
            res["debit_vals"] = None
            skip_reconciliation = True
        if recon_currency.is_zero(recon_credit_amount):
            res["credit_vals"] = None
            skip_reconciliation = True
        if skip_reconciliation:
            return res

        # ==== Match both lines together and compute amounts to reconcile ====

        # Determine which line is fully matched by the other.
        compare_amounts = recon_currency.compare_amounts(recon_debit_amount, recon_credit_amount)
        min_recon_amount = min(recon_debit_amount, recon_credit_amount)
        debit_fully_matched = compare_amounts <= 0
        credit_fully_matched = compare_amounts >= 0

        # ==== Computation of partial amounts ====
        if recon_currency == company_currency:
            # Compute the partial amount expressed in company currency.
            partial_amount = min_recon_amount

            # Compute the partial amount expressed in foreign currency.
            if debit_rate:
                partial_debit_amount_currency = debit_vals["currency"].round(
                    debit_rate * min_recon_amount
                )
                partial_debit_amount_currency = min(
                    partial_debit_amount_currency, remaining_debit_amount_curr
                )
            else:
                partial_debit_amount_currency = 0.0
            if credit_rate:
                partial_credit_amount_currency = credit_vals["currency"].round(
                    credit_rate * min_recon_amount
                )
                partial_credit_amount_currency = min(
                    partial_credit_amount_currency, -remaining_credit_amount_curr
                )
            else:
                partial_credit_amount_currency = 0.0

        else:
            # recon_currency != company_currency
            # Compute the partial amount expressed in company currency.
            if debit_rate:
                partial_debit_amount = company_currency.round(min_recon_amount / debit_rate)
                partial_debit_amount = min(partial_debit_amount, remaining_debit_amount)
            else:
                partial_debit_amount = 0.0
            if credit_rate:
                partial_credit_amount = company_currency.round(min_recon_amount / credit_rate)
                partial_credit_amount = min(partial_credit_amount, -remaining_credit_amount)
            else:
                partial_credit_amount = 0.0
            partial_amount = min(partial_debit_amount, partial_credit_amount)

            # Compute the partial amount expressed in foreign currency.
            # Take care to handle the case when a line expressed in company currency is mimicking the foreign
            # currency of the opposite line.
            if debit_vals["currency"] == company_currency:
                partial_debit_amount_currency = partial_amount
            else:
                partial_debit_amount_currency = min_recon_amount
            if credit_vals["currency"] == company_currency:
                partial_credit_amount_currency = partial_amount
            else:
                partial_credit_amount_currency = min_recon_amount

        # Computation of the partial exchange difference. You can skip this part using the
        # `no_exchange_difference` context key (when reconciling an exchange difference for example).
        if not self._context.get("no_exchange_difference"):
            exchange_lines_to_fix = self.env["account.move.line"]
            amounts_list = []
            if recon_currency == company_currency:
                if debit_fully_matched:
                    debit_exchange_amount = (
                        remaining_debit_amount_curr - partial_debit_amount_currency
                    )
                    if not debit_vals["currency"].is_zero(debit_exchange_amount):
                        if debit_vals.get("record"):
                            exchange_lines_to_fix += debit_vals["record"]
                        amounts_list.append({"amount_residual_currency": debit_exchange_amount})
                        remaining_debit_amount_curr -= debit_exchange_amount
                if credit_fully_matched:
                    credit_exchange_amount = (
                        remaining_credit_amount_curr + partial_credit_amount_currency
                    )
                    if not credit_vals["currency"].is_zero(credit_exchange_amount):
                        if credit_vals.get("record"):
                            exchange_lines_to_fix += credit_vals["record"]
                        amounts_list.append({"amount_residual_currency": credit_exchange_amount})
                        remaining_credit_amount_curr += credit_exchange_amount

            else:
                if debit_fully_matched:
                    # Create an exchange difference on the remaining amount expressed in company's currency.
                    debit_exchange_amount = remaining_debit_amount - partial_amount
                    if not company_currency.is_zero(debit_exchange_amount):
                        if debit_vals.get("record"):
                            exchange_lines_to_fix += debit_vals["record"]
                        amounts_list.append({"amount_residual": debit_exchange_amount})
                        remaining_debit_amount -= debit_exchange_amount
                        if debit_vals["currency"] == company_currency:
                            remaining_debit_amount_curr -= debit_exchange_amount
                else:
                    # Create an exchange difference ensuring the rate between the residual amounts expressed in
                    # both foreign and company's currency is still consistent regarding the rate between
                    # 'amount_currency' & 'balance'.
                    debit_exchange_amount = partial_debit_amount - partial_amount
                    if company_currency.compare_amounts(debit_exchange_amount, 0.0) > 0:
                        if debit_vals.get("record"):
                            exchange_lines_to_fix += debit_vals["record"]
                        amounts_list.append({"amount_residual": debit_exchange_amount})
                        remaining_debit_amount -= debit_exchange_amount
                        if debit_vals["currency"] == company_currency:
                            remaining_debit_amount_curr -= debit_exchange_amount

                if credit_fully_matched:
                    # Create an exchange difference on the remaining amount expressed in company's currency.
                    credit_exchange_amount = remaining_credit_amount + partial_amount
                    if not company_currency.is_zero(credit_exchange_amount):
                        if credit_vals.get("record"):
                            exchange_lines_to_fix += credit_vals["record"]
                        amounts_list.append({"amount_residual": credit_exchange_amount})
                        remaining_credit_amount -= credit_exchange_amount
                        if credit_vals["currency"] == company_currency:
                            remaining_credit_amount_curr -= credit_exchange_amount
                else:
                    # Create an exchange difference ensuring the rate between the residual amounts expressed in
                    # both foreign and company's currency is still consistent regarding the rate between
                    # 'amount_currency' & 'balance'.
                    credit_exchange_amount = partial_amount - partial_credit_amount
                    if company_currency.compare_amounts(credit_exchange_amount, 0.0) < 0:
                        if credit_vals.get("record"):
                            exchange_lines_to_fix += credit_vals["record"]
                        amounts_list.append({"amount_residual": credit_exchange_amount})
                        remaining_credit_amount -= credit_exchange_amount
                        if credit_vals["currency"] == company_currency:
                            remaining_credit_amount_curr -= credit_exchange_amount

            if exchange_lines_to_fix:
                res["exchange_vals"] = exchange_lines_to_fix._prepare_exchange_difference_move_vals(
                    amounts_list,
                    exchange_date=max(debit_vals["date"], credit_vals["date"]),
                )

        # ==== Create partials ====

        remaining_debit_amount -= partial_amount
        remaining_credit_amount += partial_amount
        remaining_debit_amount_curr -= partial_debit_amount_currency
        remaining_credit_amount_curr += partial_credit_amount_currency

        res["partial_vals"] = {
            "amount": partial_amount,
            "debit_amount_currency": partial_debit_amount_currency,
            "credit_amount_currency": partial_credit_amount_currency,
            "debit_move_id": debit_vals.get("record") and debit_vals["record"].id,
            "credit_move_id": credit_vals.get("record") and credit_vals["record"].id,
        }

        debit_vals["amount_residual"] = remaining_debit_amount
        debit_vals["amount_residual_currency"] = remaining_debit_amount_curr
        credit_vals["amount_residual"] = remaining_credit_amount
        credit_vals["amount_residual_currency"] = remaining_credit_amount_curr

        if debit_fully_matched:
            res["debit_vals"] = None
        if credit_fully_matched:
            res["credit_vals"] = None
        return res

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
                amount_currency = line.amount_currency * line.move_id.foreign_inverse_rate
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
