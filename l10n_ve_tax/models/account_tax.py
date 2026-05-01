from odoo.tools.float_utils import float_round, float_compare
from odoo import api, models, fields
from odoo.exceptions import ValidationError, UserError
from odoo.tools.misc import formatLang

import logging

_logger = logging.getLogger(__name__)


class AccountTax(models.Model):
    _inherit = "account.tax"

    @api.model
    def _prepare_tax_totals(
        self, base_lines, currency, tax_lines=None, is_company_currency_requested=False
    ):
        """
        This function adds the alternate currency tax amounts to tax_totals.
        In it, the parent function is executed 2 times, once for the original
        currency and once for the alternate currency.
        The data that is brought is not recalculated, that is, it comes from the lines of the entry
        ------
        Parameters: (Parameters inherited)
            base_lines: list of dict
            currency: res.currency
        ------
        Returns: (Return inherited)
            dict: Now returns additionally:
            "subtotal": float
            "formatted_subtotal": str
            "discount_amount": float
            "foreign_subtotal": float
            "foreign_formatted_subtotal": str
            "formatted_discount_amount": str
            "groups_by_foreign_subtotal": dict
            "foreign_discount_amount": float
            "foreign_formatted_discount_amount": str
            "foreign_subtotals": list of dict
            "foreign_amount_untaxed": float
            "foreign_amount_total": float
            "foreign_formatted_amount_untaxed": str
            "foreign_formatted_amount_total": str
        """
        foreign_currency = self.env.company.currency_foreign_id or False
        if not foreign_currency:
            raise ValidationError(_("No foreign currency configured in the company"))

        # Base Currency
        res = super()._prepare_tax_totals(
            base_lines,
            currency,
            tax_lines,
            is_company_currency_requested=is_company_currency_requested,
        )
        res_without_discount = res.copy()
        has_discount = not currency.is_zero(sum([line["discount"] for line in base_lines]))

        if has_discount:
            base_without_discount = [line.copy() for line in base_lines if line]
            for base_line in base_without_discount:
                base_line["discount"] = 0

            res_without_discount = super()._prepare_tax_totals(
                base_without_discount,
                currency,
                tax_lines,
                is_company_currency_requested=is_company_currency_requested,
            )

        foreign_base_lines, foreign_tax_lines = self.get_foreign_base_tax_lines(
            base_lines, tax_lines, foreign_currency
        )

        # Foreign Currency
        foreign_taxes = super()._prepare_tax_totals(
            foreign_base_lines,
            foreign_currency,
            foreign_tax_lines,
            is_company_currency_requested=is_company_currency_requested,
        )

        foreign_taxes_without_discount = foreign_taxes.copy()
        if has_discount:
            foreign_without_discount = [line.copy() for line in foreign_base_lines if line]
            for foreign_base_line in foreign_without_discount:
                foreign_base_line["discount"] = 0

            foreign_taxes_without_discount = super()._prepare_tax_totals(
                foreign_without_discount,
                foreign_currency,
                foreign_tax_lines,
                is_company_currency_requested=is_company_currency_requested,
            )

        res["groups_by_foreign_subtotal"] = foreign_taxes["groups_by_subtotal"]
        res["foreign_subtotals"] = foreign_taxes["subtotals"]
        res["foreign_amount_untaxed"] = foreign_taxes["amount_untaxed"]
        res["foreign_amount_total"] = foreign_taxes["amount_total"]
        res["foreign_formatted_amount_untaxed"] = foreign_taxes["formatted_amount_untaxed"]
        res["foreign_formatted_amount_total"] = foreign_taxes["formatted_amount_total"]

        res["show_discount"] = self.env.company.show_discount_on_moves

        res["subtotal"] = res_without_discount["amount_untaxed"]
        res["formatted_subtotal"] = formatLang(self.env, res["subtotal"], currency_obj=currency)

        res["foreign_subtotal"] = foreign_taxes_without_discount["amount_untaxed"]
        res["foreign_formatted_subtotal"] = formatLang(
            self.env, res["foreign_subtotal"], currency_obj=foreign_currency
        )

        res["discount_amount"] = res["amount_untaxed"] - res_without_discount["amount_untaxed"]
        res["formatted_discount_amount"] = formatLang(
            self.env, res["discount_amount"], currency_obj=currency
        )
        res["foreign_discount_amount"] = (
            foreign_taxes["amount_untaxed"] - foreign_taxes_without_discount["amount_untaxed"]
        )
        res["foreign_formatted_discount_amount"] = formatLang(
            self.env, res["foreign_discount_amount"], currency_obj=foreign_currency
        )

        move = self._get_move_from_base_lines(base_lines)

        amounts = self._get_total_paid_foreign(move, foreign_currency) if move else []


        res["foreign_total_amount_paid"] = sum(amounts)
           

        foreign_amount_total = res.get('foreign_amount_total', 0.0)

        raw_residual = foreign_amount_total - res.get("foreign_total_amount_paid", 0.0)
        
        if float_is_zero(raw_residual, precision_digits=foreign_currency.decimal_places):
            res["foreign_total_residual"] = 0.0
            formatted_result = 0.0
        else:
            res["foreign_total_residual"] = raw_residual
            formatted_result = 0.0 if raw_residual < 0 else raw_residual
            
        res["foreign_formatted_total_residual"] = formatLang(
            self.env,
            formatted_result,
            currency_obj=foreign_currency
        )            

        return res

    def _get_move_from_base_lines(self, base_lines):
        for l in (base_lines or []):
            r = l.get("record")
            if not r:
                continue

            if getattr(r, "_name", None) == "account.move":
                return r

            if "move_id" in getattr(r, "_fields", {}):
                if r.move_id:
                    return r.move_id
        return None

    def _get_total_paid_foreign(self, move, foreign_currency):
        if not move or not move.invoice_payments_widget:
            return []

        amounts = []
        # Odoo almacena esto como dict o como string JSON dependiendo de la versión/estado
        widget_data = move.invoice_payments_widget
        content = widget_data.get('content') or []

        for payment in content:
            # Extraemos directamente el valor que vemos en tu imagen
            # Usamos .get() por seguridad si el campo no existe en algún pago
            
            f_amount = payment.get('foreign_amount', 0.0)

            # Opcional: Validar que el pago sea de la moneda que buscas
            # En tu imagen sale 'foreign_id': 2
            amounts.append(f_amount)

        return amounts

    def get_foreign_base_tax_lines(self, base_lines, tax_lines, currency):
        foreign_base_lines = [line.copy() for line in base_lines if line]
        foreign_tax_lines = None
        if tax_lines:
            foreign_tax_lines = [line.copy() for line in tax_lines if line]
        taxes = []
        for base_line in foreign_base_lines:
            is_exists_foreign_price = "foreign_price" in base_line["record"]
            base_line["currency"] = currency
            if is_exists_foreign_price:
                
                rate = base_line["record"].foreign_inverse_rate
                base_line["price_unit"] = base_line["record"].price_unit * rate
                base_line["price_subtotal"] = base_line["record"].price_subtotal * rate

            else:
                if not rate:
                    move = base_line["record"].move_id
                    rate = move.foreign_inverse_rate or self.env['res.currency.rate'].compute_rate(move.foreign_currency_id.id, move.invoice_date or fields.Date.today()).get('foreign_inverse_rate', 0.0)
                
                base_line["price_unit"] = base_line["record"].price_unit * rate
                base_line["price_subtotal"] = base_line["record"].price_subtotal * rate

            if base_line["taxes"]:
                taxes.append(
                    {
                        "tax": base_line["taxes"][0],
                        "price": base_line["price_unit"],
                        "base": base_line["price_subtotal"],
                    }
                )

        tax_values_list = []
        for base_line in foreign_base_lines:
            tax_values_list += self._compute_taxes_for_single_line(base_line)[1]

        round_globally = self.env.company.tax_calculation_rounding_method == "round_globally"

        if foreign_tax_lines:
            for tax_line in foreign_tax_lines:
                tax_line["currency"] = currency
                tax_line["tax_amount"] = 0.0
                amount = 0.0
                for tax in tax_values_list:
                    if tax["tax_repartition_line"].id == tax_line["tax_repartition_line"].id:
                        if not round_globally:
                            amount += float_round(
                                tax["amount"], precision_digits=currency.decimal_places
                            )
                        else:
                            amount += tax["amount"]

                tax_line["tax_amount"] = float_round(
                    amount, precision_digits=currency.decimal_places
                )

        return foreign_base_lines, foreign_tax_lines

    def compute_all(self, price_unit, currency=None, quantity=1.0, product=None, partner=None, is_refund=False, handle_price_include=True, include_caba_tags=False, fixed_multiplicator=1):
        """Compute all information required to apply taxes (in self + their children in case of a tax group).
        We consider the sequence of the parent for group of taxes.
            Eg. considering letters as taxes and alphabetic order as sequence :
            [G, B([A, D, F]), E, C] will be computed as [A, D, F, C, E, G]



        :param price_unit: The unit price of the line to compute taxes on.
        :param currency: The optional currency in which the price_unit is expressed.
        :param quantity: The optional quantity of the product to compute taxes on.
        :param product: The optional product to compute taxes on.
            Used to get the tags to apply on the lines.
        :param partner: The optional partner compute taxes on.
            Used to retrieve the lang to build strings and for potential extensions.
        :param is_refund: The optional boolean indicating if this is a refund.
        :param handle_price_include: Used when we need to ignore all tax included in price. If False, it means the
            amount passed to this method will be considered as the base of all computations.
        :param include_caba_tags: The optional boolean indicating if CABA tags need to be taken into account.
        :param fixed_multiplicator: The amount to multiply fixed amount taxes by.
        :return: {
            'total_excluded': 0.0,    # Total without taxes
            'total_included': 0.0,    # Total with taxes
            'total_void'    : 0.0,    # Total with those taxes, that don't have an account set
            'base_tags: : list<int>,  # Tags to apply on the base line
            'taxes': [{               # One dict for each tax in self and their children
                'id': int,
                'name': str,
                'amount': float,
                'base': float,
                'sequence': int,
                'account_id': int,
                'refund_account_id': int,
                'analytic': bool,
                'price_include': bool,
                'tax_exigibility': str,
                'tax_repartition_line_id': int,
                'group': recordset,
                'tag_ids': list<int>,
                'tax_ids': list<int>,
            }],
        } """
        if not self:
            company = self.env.company
        else:
            company = self[0].company_id._accessible_branches()[:1] or self[0].company_id

        # 1) Flatten the taxes.
        taxes, groups_map = self.flatten_taxes_hierarchy(create_map=True)

        # 2) Deal with the rounding methods
        if not currency:
            currency = company.currency_id

        # By default, for each tax, tax amount will first be computed
        # and rounded at the 'Account' decimal precision for each
        # PO/SO/invoice line and then these rounded amounts will be
        # summed, leading to the total amount for that tax. But, if the
        # company has tax_calculation_rounding_method = round_globally,
        # we still follow the same method, but we use a much larger
        # precision when we round the tax amount for each line (we use
        # the 'Account' decimal precision + 5), and that way it's like
        # rounding after the sum of the tax amounts of each line
        prec = currency.rounding
        # In some cases, it is necessary to force/prevent the rounding of the tax and the total
        # amounts. For example, in SO/PO line, we don't want to round the price unit at the
        # precision of the currency.
        # The context key 'round' allows to force the standard behavior.
        round_tax = False if company.tax_calculation_rounding_method == 'round_globally' else True
        if 'round' in self.env.context:
            round_tax = bool(self.env.context['round'])

        prec = currency.rounding
        if self._context.get('round_base') is False:
            prec = 0.000000001

        # 3) Iterate the taxes in the reversed sequence order to retrieve the initial base of the computation.
        #     tax  |  base  |  amount  |
        # /\ ----------------------------
        # || tax_1 |  XXXX  |          | <- we are looking for that, it's the total_excluded
        # || tax_2 |   ..   |          |
        # || tax_3 |   ..   |          |
        # ||  ...  |   ..   |    ..    |
        #    ----------------------------
        def recompute_base(base_amount, incl_tax_amounts):
            """ Recompute the new base amount based on included fixed/percent amounts and the current base amount. """
            fixed_amount = incl_tax_amounts['fixed_amount']
            division_amount = sum(tax_factor for _i, tax_factor in incl_tax_amounts['division_taxes'])
            percent_amount = sum(tax_amount * sum_repartition_factor for _i, tax_amount, sum_repartition_factor in incl_tax_amounts['percent_taxes'])

            if company.country_code == 'IN':
                # For the indian case, when facing two percent price-included taxes having the same percentage,
                # both need to produce the same tax amounts. To do that, the tax amount of those taxes are computed
                # directly during the first traveling in reversed order.
                total_tax_amount = 0.0
                for i, tax_amount, sum_repartition_factor in incl_tax_amounts['percent_taxes']:
                    gross_tax_amount = float_round(base * tax_amount / (100 + percent_amount), precision_rounding=prec)
                    factored_tax_amount = float_round(gross_tax_amount * sum_repartition_factor, precision_rounding=prec)
                    total_tax_amount += factored_tax_amount
                    cached_tax_amounts[i] = gross_tax_amount
                    fixed_amount += factored_tax_amount
                for i, _tax_amount, _sum_repartition_factor in incl_tax_amounts['percent_taxes']:
                    cached_base_amounts[i] = base - total_tax_amount
                percent_amount = 0.0

            incl_tax_amounts.update({
                'percent_taxes': [],
                'division_taxes': [],
                'fixed_amount': 0.0,
            })

            return (base_amount - fixed_amount) / (1.0 + percent_amount / 100.0) * (100 - division_amount) / 100

        # The first/last base must absolutely be rounded to work in round globally.
        # Indeed, the sum of all taxes ('taxes' key in the result dictionary) must be strictly equals to
        # 'price_included' - 'price_excluded' whatever the rounding method.
        #
        # Example using the global rounding without any decimals:
        # Suppose two invoice lines: 27000 and 10920, both having a 19% price included tax.
        #
        #                   Line 1                      Line 2
        # -----------------------------------------------------------------------
        # total_included:   27000                       10920
        # tax:              27000 / 1.19 = 4310.924     10920 / 1.19 = 1743.529
        # total_excluded:   22689.076                   9176.471
        #
        # If the rounding of the total_excluded isn't made at the end, it could lead to some rounding issues
        # when summing the tax amounts, e.g. on invoices.
        # In that case:
        #  - amount_untaxed will be 22689 + 9176 = 31865
        #  - amount_tax will be 4310.924 + 1743.529 = 6054.453 ~ 6054
        #  - amount_total will be 31865 + 6054 = 37919 != 37920 = 27000 + 10920
        #
        # By performing a rounding at the end to compute the price_excluded amount, the amount_tax will be strictly
        # equals to 'price_included' - 'price_excluded' after rounding and then:
        #   Line 1: sum(taxes) = 27000 - 22689 = 4311
        #   Line 2: sum(taxes) = 10920 - 2176 = 8744
        #   amount_tax = 4311 + 8744 = 13055
        #   amount_total = 31865 + 13055 = 37920

        base = price_unit * quantity

        if self._context.get('round_base', True):
            base = currency.round(base)

        # For the computation of move lines, we could have a negative base value.
        # In this case, compute all with positive values and negate them at the end.
        sign = 1
        if currency.is_zero(base):
            sign = -1 if fixed_multiplicator < 0 else 1
        elif base < 0:
            sign = -1
            base = -base

        # Store the totals to reach when using price_include taxes (only the last price included in row)
        total_included_checkpoints = {}
        i = len(taxes) - 1
        store_included_tax_total = True
        # Keep track of the accumulated included fixed/percent amount.
        incl_tax_amounts = {
            'percent_taxes': [],
            'division_taxes': [],
            'fixed_amount': 0.0,
        }
        custom_fixed_amount_after = 0.0
        # Store the tax amounts we compute while searching for the total_excluded
        cached_base_amounts = {}
        cached_tax_amounts = {}
        is_base_affected = True
        if handle_price_include:
            for tax in reversed(taxes):
                tax_repartition_lines = (
                    is_refund
                    and tax.refund_repartition_line_ids
                    or tax.invoice_repartition_line_ids
                ).filtered(lambda x: x.repartition_type == "tax")
                sum_repartition_factor = sum(tax_repartition_lines.mapped("factor"))

                if tax.include_base_amount and is_base_affected:
                    base = recompute_base(base, incl_tax_amounts)
                    store_included_tax_total = True
                if self._context.get('force_price_include', tax.price_include):
                    if tax.amount_type == 'percent':
                        incl_tax_amounts['percent_taxes'].append((i, tax.amount, sum_repartition_factor))
                    elif tax.amount_type == 'division':
                        incl_tax_amounts['division_taxes'].append((i, tax.amount * sum_repartition_factor))
                    elif tax.amount_type == 'fixed':
                        incl_tax_amounts['fixed_amount'] = abs(quantity) * tax.amount * sum_repartition_factor * abs(fixed_multiplicator)
                    else:
                        # tax.amount_type == other (python)
                        tax_amount = tax._compute_amount(base, sign * price_unit, quantity, product, partner, fixed_multiplicator)
                        tax_amount = float_round(tax_amount, precision_rounding=prec)
                        incl_tax_amounts['fixed_amount'] += tax_amount
                        # Avoid unecessary re-computation
                        cached_tax_amounts[i] = tax_amount
                        custom_fixed_amount_after += tax_amount
                    # In case of a zero tax, do not store the base amount since the tax amount will
                    # be zero anyway. Group and Python taxes have an amount of zero, so do not take
                    # them into account.
                    if (
                        store_included_tax_total
                        and (tax.amount or tax.amount_type not in ("percent", "division", "fixed"))
                        and i not in cached_tax_amounts
                    ):
                        total_included_checkpoints[i] = base - custom_fixed_amount_after
                        store_included_tax_total = False
                        custom_fixed_amount_after = 0.0
                i -= 1
                is_base_affected = tax.is_base_affected

        total_excluded = recompute_base(base, incl_tax_amounts)
        if self._context.get('round_base', True):
            total_excluded = currency.round(total_excluded)

        # 4) Iterate the taxes in the sequence order to compute missing tax amounts.
        # Start the computation of accumulated amounts at the total_excluded value.
        base = total_included = total_void = total_excluded

        # Flag indicating the checkpoint used in price_include to avoid rounding issue must be skipped since the base
        # amount has changed because we are currently mixing price-included and price-excluded include_base_amount
        # taxes.
        skip_checkpoint = False

        # Get product tags, account.account.tag objects that need to be injected in all
        # the tax_tag_ids of all the move lines created by the compute all for this product.
        product_tag_ids = product.sudo().account_tag_ids.ids if product else []

        taxes_vals = []
        i = 0
        cumulated_tax_included_amount = 0
        for tax in taxes:
            price_include = self._context.get('force_price_include', tax.price_include)

            if price_include and i in cached_base_amounts:
                tax_base_amount = cached_base_amounts[i]
            elif price_include or tax.is_base_affected:
                tax_base_amount = base
            else:
                tax_base_amount = total_excluded

            tax_repartition_lines = (is_refund and tax.refund_repartition_line_ids or tax.invoice_repartition_line_ids).filtered(lambda x: x.repartition_type == 'tax')
            sum_repartition_factor = sum(tax_repartition_lines.mapped('factor'))

            #compute the tax_amount
            if price_include and i in cached_tax_amounts:
                tax_amount = cached_tax_amounts[i]
            elif not skip_checkpoint and price_include and total_included_checkpoints.get(i) is not None and sum_repartition_factor != 0:
                # We know the total to reach for that tax, so we make a substraction to avoid any rounding issues
                tax_amount = total_included_checkpoints[i] - (base + cumulated_tax_included_amount)
                cumulated_tax_included_amount = 0
            else:
                tax_amount = tax.with_context(force_price_include=False)._compute_amount(
                    tax_base_amount, sign * price_unit, quantity, product, partner, fixed_multiplicator)

            # Round the tax_amount multiplied by the computed repartition lines factor.
            
            factorized_tax_amount = float_round(tax_amount * sum_repartition_factor, precision_rounding=prec)

            if price_include and total_included_checkpoints.get(i) is None:
                cumulated_tax_included_amount += factorized_tax_amount

            # If the tax affects the base of subsequent taxes, its tax move lines must
            # receive the base tags and tag_ids of these taxes, so that the tax report computes
            # the right total
            subsequent_taxes = self.env['account.tax']
            subsequent_tags = self.env['account.account.tag']
            if tax.include_base_amount:
                subsequent_taxes = taxes[i+1:].filtered('is_base_affected')

                taxes_for_subsequent_tags = subsequent_taxes

                if not include_caba_tags:
                    taxes_for_subsequent_tags = subsequent_taxes.filtered(lambda x: x.tax_exigibility != 'on_payment')

                subsequent_tags = taxes_for_subsequent_tags.get_tax_tags(is_refund, 'base')

            # Compute the tax line amounts by multiplying each factor with the tax amount.
            # Then, spread the tax rounding to ensure the consistency of each line independently with the factorized
            # amount. E.g:
            #
            # Suppose a tax having 4 x 50% repartition line applied on a tax amount of 0.03 with 2 decimal places.
            # The factorized_tax_amount will be 0.06 (200% x 0.03). However, each line taken independently will compute
            # 50% * 0.03 = 0.01 with rounding. It means there is 0.06 - 0.04 = 0.02 as total_rounding_error to dispatch
            # in lines as 2 x 0.01.
            # repartition_line_amounts = [float_round(tax_amount * line.factor, precision_rounding=prec) for line in tax_repartition_lines]
            line_factor = [line.factor for line in tax_repartition_lines]                        
            
            repartition_line_amounts = [tax_amount]           
            total_rounding_error = float_round(factorized_tax_amount - sum(repartition_line_amounts), precision_rounding=prec)
            nber_rounding_steps = int(abs(total_rounding_error / currency.rounding))
            rounding_error = float_round(nber_rounding_steps and total_rounding_error / nber_rounding_steps or 0.0, precision_rounding=prec)

            for repartition_line, line_amount in zip(tax_repartition_lines, repartition_line_amounts):
                if nber_rounding_steps:
                    line_amount += rounding_error
                    nber_rounding_steps -= 1

                if not include_caba_tags and tax.tax_exigibility == 'on_payment':
                    repartition_line_tags = self.env['account.account.tag']
                else:
                    repartition_line_tags = repartition_line.tag_ids

                taxes_vals.append({
                    'id': tax.id,
                    'name': partner and tax.with_context(lang=partner.lang).name or tax.name,
                    'amount': sign * line_amount,
                    'base': float_round(sign * tax_base_amount, precision_rounding=prec),
                    'sequence': tax.sequence,
                    'account_id': repartition_line._get_aml_target_tax_account(force_caba_exigibility=include_caba_tags).id,
                    'analytic': tax.analytic,
                    'use_in_tax_closing': repartition_line.use_in_tax_closing,
                    'price_include': price_include,
                    'tax_exigibility': tax.tax_exigibility,
                    'tax_repartition_line_id': repartition_line.id,
                    'group': groups_map.get(tax),
                    'tag_ids': (repartition_line_tags + subsequent_tags).ids + product_tag_ids,
                    'tax_ids': subsequent_taxes.ids,
                })

                if not repartition_line.account_id:
                    total_void += line_amount

            # Affect subsequent taxes
            if tax.include_base_amount:
                base += factorized_tax_amount
                if not price_include:
                    skip_checkpoint = True

            total_included += factorized_tax_amount
            i += 1

        base_taxes_for_tags = taxes
        if not include_caba_tags:
            base_taxes_for_tags = base_taxes_for_tags.filtered(lambda x: x.tax_exigibility != 'on_payment')

        base_rep_lines = base_taxes_for_tags.mapped(is_refund and 'refund_repartition_line_ids' or 'invoice_repartition_line_ids').filtered(lambda x: x.repartition_type == 'base')
        round_base = self._context.get('round_base', True)
        if round_base:
            total_included = currency.round(total_included)
        return {
            'base_tags': base_rep_lines.tag_ids.ids + product_tag_ids,
            'taxes': taxes_vals,
            'total_excluded': sign * total_excluded,
            'total_included': sign * total_included,
            'total_void': sign * total_void,
        }

    def compute_all(self, price_unit, currency=None, quantity=1.0, product=None, partner=None, is_refund=False, handle_price_include=True, include_caba_tags=False, fixed_multiplicator=1):
        """Compute all information required to apply taxes (in self + their children in case of a tax group).
        We consider the sequence of the parent for group of taxes.
            Eg. considering letters as taxes and alphabetic order as sequence :
            [G, B([A, D, F]), E, C] will be computed as [A, D, F, C, E, G]



        :param price_unit: The unit price of the line to compute taxes on.
        :param currency: The optional currency in which the price_unit is expressed.
        :param quantity: The optional quantity of the product to compute taxes on.
        :param product: The optional product to compute taxes on.
            Used to get the tags to apply on the lines.
        :param partner: The optional partner compute taxes on.
            Used to retrieve the lang to build strings and for potential extensions.
        :param is_refund: The optional boolean indicating if this is a refund.
        :param handle_price_include: Used when we need to ignore all tax included in price. If False, it means the
            amount passed to this method will be considered as the base of all computations.
        :param include_caba_tags: The optional boolean indicating if CABA tags need to be taken into account.
        :param fixed_multiplicator: The amount to multiply fixed amount taxes by.
        :return: {
            'total_excluded': 0.0,    # Total without taxes
            'total_included': 0.0,    # Total with taxes
            'total_void'    : 0.0,    # Total with those taxes, that don't have an account set
            'base_tags: : list<int>,  # Tags to apply on the base line
            'taxes': [{               # One dict for each tax in self and their children
                'id': int,
                'name': str,
                'amount': float,
                'base': float,
                'sequence': int,
                'account_id': int,
                'refund_account_id': int,
                'analytic': bool,
                'price_include': bool,
                'tax_exigibility': str,
                'tax_repartition_line_id': int,
                'group': recordset,
                'tag_ids': list<int>,
                'tax_ids': list<int>,
            }],
        } """
        if not self:
            company = self.env.company
        else:
            company = self[0].company_id._accessible_branches()[:1] or self[0].company_id

        # 1) Flatten the taxes.
        taxes, groups_map = self.flatten_taxes_hierarchy(create_map=True)

        # 2) Deal with the rounding methods
        if not currency:
            currency = company.currency_id

        # By default, for each tax, tax amount will first be computed
        # and rounded at the 'Account' decimal precision for each
        # PO/SO/invoice line and then these rounded amounts will be
        # summed, leading to the total amount for that tax. But, if the
        # company has tax_calculation_rounding_method = round_globally,
        # we still follow the same method, but we use a much larger
        # precision when we round the tax amount for each line (we use
        # the 'Account' decimal precision + 5), and that way it's like
        # rounding after the sum of the tax amounts of each line
        prec = currency.rounding

        # In some cases, it is necessary to force/prevent the rounding of the tax and the total
        # amounts. For example, in SO/PO line, we don't want to round the price unit at the
        # precision of the currency.
        # The context key 'round' allows to force the standard behavior.
        round_tax = False if company.tax_calculation_rounding_method == 'round_globally' else True
        if 'round' in self.env.context:
            round_tax = bool(self.env.context['round'])

        if not round_tax:
            prec *= 1e-5

        # 3) Iterate the taxes in the reversed sequence order to retrieve the initial base of the computation.
        #     tax  |  base  |  amount  |
        # /\ ----------------------------
        # || tax_1 |  XXXX  |          | <- we are looking for that, it's the total_excluded
        # || tax_2 |   ..   |          |
        # || tax_3 |   ..   |          |
        # ||  ...  |   ..   |    ..    |
        #    ----------------------------
        def recompute_base(base_amount, incl_tax_amounts):
            """ Recompute the new base amount based on included fixed/percent amounts and the current base amount. """
            fixed_amount = incl_tax_amounts['fixed_amount']
            division_amount = sum(tax_factor for _i, tax_factor in incl_tax_amounts['division_taxes'])
            percent_amount = sum(tax_amount * sum_repartition_factor for _i, tax_amount, sum_repartition_factor in incl_tax_amounts['percent_taxes'])

            if company.country_code == 'IN':
                # For the indian case, when facing two percent price-included taxes having the same percentage,
                # both need to produce the same tax amounts. To do that, the tax amount of those taxes are computed
                # directly during the first traveling in reversed order.
                total_tax_amount = 0.0
                for i, tax_amount, sum_repartition_factor in incl_tax_amounts['percent_taxes']:
                    gross_tax_amount = float_round(base * tax_amount / (100 + percent_amount), precision_rounding=prec)
                    factored_tax_amount = float_round(gross_tax_amount * sum_repartition_factor, precision_rounding=prec)
                    total_tax_amount += factored_tax_amount
                    cached_tax_amounts[i] = gross_tax_amount
                    fixed_amount += factored_tax_amount
                for i, _tax_amount, _sum_repartition_factor in incl_tax_amounts['percent_taxes']:
                    cached_base_amounts[i] = base - total_tax_amount
                percent_amount = 0.0

            incl_tax_amounts.update({
                'percent_taxes': [],
                'division_taxes': [],
                'fixed_amount': 0.0,
            })

            return (base_amount - fixed_amount) / (1.0 + percent_amount / 100.0) * (100 - division_amount) / 100

        # The first/last base must absolutely be rounded to work in round globally.
        # Indeed, the sum of all taxes ('taxes' key in the result dictionary) must be strictly equals to
        # 'price_included' - 'price_excluded' whatever the rounding method.
        #
        # Example using the global rounding without any decimals:
        # Suppose two invoice lines: 27000 and 10920, both having a 19% price included tax.
        #
        #                   Line 1                      Line 2
        # -----------------------------------------------------------------------
        # total_included:   27000                       10920
        # tax:              27000 / 1.19 = 4310.924     10920 / 1.19 = 1743.529
        # total_excluded:   22689.076                   9176.471
        #
        # If the rounding of the total_excluded isn't made at the end, it could lead to some rounding issues
        # when summing the tax amounts, e.g. on invoices.
        # In that case:
        #  - amount_untaxed will be 22689 + 9176 = 31865
        #  - amount_tax will be 4310.924 + 1743.529 = 6054.453 ~ 6054
        #  - amount_total will be 31865 + 6054 = 37919 != 37920 = 27000 + 10920
        #
        # By performing a rounding at the end to compute the price_excluded amount, the amount_tax will be strictly
        # equals to 'price_included' - 'price_excluded' after rounding and then:
        #   Line 1: sum(taxes) = 27000 - 22689 = 4311
        #   Line 2: sum(taxes) = 10920 - 2176 = 8744
        #   amount_tax = 4311 + 8744 = 13055
        #   amount_total = 31865 + 13055 = 37920
        base = price_unit * quantity
        if self._context.get('round_base', True):
            base = currency.round(base)

        # For the computation of move lines, we could have a negative base value.
        # In this case, compute all with positive values and negate them at the end.
        sign = 1
        if currency.is_zero(base):
            sign = -1 if fixed_multiplicator < 0 else 1
        elif base < 0:
            sign = -1
            base = -base

        # Store the totals to reach when using price_include taxes (only the last price included in row)
        total_included_checkpoints = {}
        i = len(taxes) - 1
        store_included_tax_total = True
        # Keep track of the accumulated included fixed/percent amount.
        incl_tax_amounts = {
            'percent_taxes': [],
            'division_taxes': [],
            'fixed_amount': 0.0,
        }
        custom_fixed_amount_after = 0.0
        # Store the tax amounts we compute while searching for the total_excluded
        cached_base_amounts = {}
        cached_tax_amounts = {}
        is_base_affected = True
        if handle_price_include:
            for tax in reversed(taxes):
                tax_repartition_lines = (
                    is_refund
                    and tax.refund_repartition_line_ids
                    or tax.invoice_repartition_line_ids
                ).filtered(lambda x: x.repartition_type == "tax")
                sum_repartition_factor = sum(tax_repartition_lines.mapped("factor"))

                if tax.include_base_amount and is_base_affected:
                    base = recompute_base(base, incl_tax_amounts)
                    store_included_tax_total = True
                if self._context.get('force_price_include', tax.price_include):
                    if tax.amount_type == 'percent':
                        incl_tax_amounts['percent_taxes'].append((i, tax.amount, sum_repartition_factor))
                    elif tax.amount_type == 'division':
                        incl_tax_amounts['division_taxes'].append((i, tax.amount * sum_repartition_factor))
                    elif tax.amount_type == 'fixed':
                        incl_tax_amounts['fixed_amount'] = abs(quantity) * tax.amount * sum_repartition_factor * abs(fixed_multiplicator)
                    else:
                        # tax.amount_type == other (python)
                        tax_amount = tax._compute_amount(base, sign * price_unit, quantity, product, partner, fixed_multiplicator)
                        tax_amount = float_round(tax_amount, precision_rounding=prec)
                        incl_tax_amounts['fixed_amount'] += tax_amount
                        # Avoid unecessary re-computation
                        cached_tax_amounts[i] = tax_amount
                        custom_fixed_amount_after += tax_amount
                    # In case of a zero tax, do not store the base amount since the tax amount will
                    # be zero anyway. Group and Python taxes have an amount of zero, so do not take
                    # them into account.
                    if (
                        store_included_tax_total
                        and (tax.amount or tax.amount_type not in ("percent", "division", "fixed"))
                        and i not in cached_tax_amounts
                    ):
                        total_included_checkpoints[i] = base - custom_fixed_amount_after
                        store_included_tax_total = False
                        custom_fixed_amount_after = 0.0
                i -= 1
                is_base_affected = tax.is_base_affected

        total_excluded = recompute_base(base, incl_tax_amounts)
        if self._context.get('round_base', True):
            total_excluded = currency.round(total_excluded)

        # 4) Iterate the taxes in the sequence order to compute missing tax amounts.
        # Start the computation of accumulated amounts at the total_excluded value.
        base = total_included = total_void = total_excluded

        # Flag indicating the checkpoint used in price_include to avoid rounding issue must be skipped since the base
        # amount has changed because we are currently mixing price-included and price-excluded include_base_amount
        # taxes.
        skip_checkpoint = False

        # Get product tags, account.account.tag objects that need to be injected in all
        # the tax_tag_ids of all the move lines created by the compute all for this product.
        product_tag_ids = product.sudo().account_tag_ids.ids if product else []

        taxes_vals = []
        i = 0
        cumulated_tax_included_amount = 0
        for tax in taxes:
            price_include = self._context.get('force_price_include', tax.price_include)

            if price_include and i in cached_base_amounts:
                tax_base_amount = cached_base_amounts[i]
            elif price_include or tax.is_base_affected:
                tax_base_amount = base
            else:
                tax_base_amount = total_excluded

            tax_repartition_lines = (is_refund and tax.refund_repartition_line_ids or tax.invoice_repartition_line_ids).filtered(lambda x: x.repartition_type == 'tax')
            sum_repartition_factor = sum(tax_repartition_lines.mapped('factor'))

            #compute the tax_amount
            if price_include and i in cached_tax_amounts:
                tax_amount = cached_tax_amounts[i]
            elif not skip_checkpoint and price_include and total_included_checkpoints.get(i) is not None and sum_repartition_factor != 0:
                # We know the total to reach for that tax, so we make a substraction to avoid any rounding issues
                tax_amount = total_included_checkpoints[i] - (base + cumulated_tax_included_amount)
                cumulated_tax_included_amount = 0
            else:
                tax_amount = tax.with_context(force_price_include=False)._compute_amount(
                    tax_base_amount, sign * price_unit, quantity, product, partner, fixed_multiplicator)

            # Round the tax_amount multiplied by the computed repartition lines factor.
            tax_amount = float_round(tax_amount, precision_rounding=prec)
            factorized_tax_amount = float_round(tax_amount * sum_repartition_factor, precision_rounding=prec)

            if price_include and total_included_checkpoints.get(i) is None:
                cumulated_tax_included_amount += factorized_tax_amount

            # If the tax affects the base of subsequent taxes, its tax move lines must
            # receive the base tags and tag_ids of these taxes, so that the tax report computes
            # the right total
            subsequent_taxes = self.env['account.tax']
            subsequent_tags = self.env['account.account.tag']
            if tax.include_base_amount:
                subsequent_taxes = taxes[i+1:].filtered('is_base_affected')

                taxes_for_subsequent_tags = subsequent_taxes

                if not include_caba_tags:
                    taxes_for_subsequent_tags = subsequent_taxes.filtered(lambda x: x.tax_exigibility != 'on_payment')

                subsequent_tags = taxes_for_subsequent_tags.get_tax_tags(is_refund, 'base')

            # Compute the tax line amounts by multiplying each factor with the tax amount.
            # Then, spread the tax rounding to ensure the consistency of each line independently with the factorized
            # amount. E.g:
            #
            # Suppose a tax having 4 x 50% repartition line applied on a tax amount of 0.03 with 2 decimal places.
            # The factorized_tax_amount will be 0.06 (200% x 0.03). However, each line taken independently will compute
            # 50% * 0.03 = 0.01 with rounding. It means there is 0.06 - 0.04 = 0.02 as total_rounding_error to dispatch
            # in lines as 2 x 0.01.
            repartition_line_amounts = [float_round(tax_amount * line.factor, precision_rounding=prec) for line in tax_repartition_lines]
            total_rounding_error = float_round(factorized_tax_amount - sum(repartition_line_amounts), precision_rounding=prec)
            nber_rounding_steps = int(abs(total_rounding_error / currency.rounding))
            rounding_error = float_round(nber_rounding_steps and total_rounding_error / nber_rounding_steps or 0.0, precision_rounding=prec)

            for repartition_line, line_amount in zip(tax_repartition_lines, repartition_line_amounts):

                if nber_rounding_steps:
                    line_amount += rounding_error
                    nber_rounding_steps -= 1

                if not include_caba_tags and tax.tax_exigibility == 'on_payment':
                    repartition_line_tags = self.env['account.account.tag']
                else:
                    repartition_line_tags = repartition_line.tag_ids

                taxes_vals.append({
                    'id': tax.id,
                    'name': partner and tax.with_context(lang=partner.lang).name or tax.name,
                    'amount': sign * line_amount,
                    'base': float_round(sign * tax_base_amount, precision_rounding=prec),
                    'sequence': tax.sequence,
                    'account_id': repartition_line._get_aml_target_tax_account(force_caba_exigibility=include_caba_tags).id,
                    'analytic': tax.analytic,
                    'use_in_tax_closing': repartition_line.use_in_tax_closing,
                    'price_include': price_include,
                    'tax_exigibility': tax.tax_exigibility,
                    'tax_repartition_line_id': repartition_line.id,
                    'group': groups_map.get(tax),
                    'tag_ids': (repartition_line_tags + subsequent_tags).ids + product_tag_ids,
                    'tax_ids': subsequent_taxes.ids,
                })

                if not repartition_line.account_id:
                    total_void += line_amount

            # Affect subsequent taxes
            if tax.include_base_amount:
                base += factorized_tax_amount
                if not price_include:
                    skip_checkpoint = True

            total_included += factorized_tax_amount
            i += 1

        base_taxes_for_tags = taxes
        if not include_caba_tags:
            base_taxes_for_tags = base_taxes_for_tags.filtered(lambda x: x.tax_exigibility != 'on_payment')

        base_rep_lines = base_taxes_for_tags.mapped(is_refund and 'refund_repartition_line_ids' or 'invoice_repartition_line_ids').filtered(lambda x: x.repartition_type == 'base')
        round_base = self._context.get('round_base', True)
        if round_base:
            total_included = currency.round(total_included)
        return {
            'base_tags': base_rep_lines.tag_ids.ids + product_tag_ids,
            'taxes': taxes_vals,
            'total_excluded': sign * total_excluded,
            'total_included': sign * total_included,
            'total_void': sign * total_void,
        }