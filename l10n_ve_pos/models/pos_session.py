from odoo import models, fields, api, _, Command
from odoo.tools import float_is_zero, float_compare
from odoo.osv.expression import AND, OR
from odoo.exceptions import ValidationError
import logging
import math

_logger = logging.getLogger(__name__)


class PosSession(models.Model):
    _inherit = "pos.session"

    foreign_currency_id = fields.Many2one(
        "res.currency",
        related="config_id.foreign_currency_id",
        string="Foreign Currency",
    )

    # @override
    def _loader_params_res_company(self):
        return {
            "search_params": {
                "domain": [("id", "=", self.company_id.id)],
                "fields": [
                    "currency_id",
                    "email",
                    "street",
                    "website",
                    "company_registry",
                    "vat",
                    "name",
                    "phone",
                    "partner_id",
                    "country_id",
                    "state_id",
                    "tax_calculation_rounding_method",
                    "nomenclature_id",
                    "point_of_sale_use_ticket_qr_code",
                    "point_of_sale_ticket_unique_code",
                    "account_fiscal_country_id",
                ],
            }
        }

    def load_pos_data(self):
        res = super().load_pos_data()
        res["prefix_vats"] = self.env["res.partner"]._fields["prefix_vat"].selection
        return res

    def _loader_params_pos_payment(self):
        res = super()._loader_params_pos_payment()
        res["search_params"]["fields"].append("foreign_rate")
        return res

    def _loader_params_pos_payment_method(self):
        res = super()._loader_params_pos_payment_method()
        res["search_params"]["fields"].append("is_foreign_currency")
        return res

    def _loader_params_account_tax(self):
        res = super()._loader_params_account_tax()
        res["search_params"]["fields"].append("type_tax_use")
        return res

    def _loader_params_res_partner(self):
        res = super()._loader_params_res_partner()
        res["search_params"]["fields"].append("prefix_vat")
        res["search_params"]["fields"].append("city_id")
        return res

    def _loader_params_res_currency(self):
        """
        This method is used to get the params for the search_read of res.currency
        """
        res = super()._loader_params_res_currency()
        res["search_params"]["domain"] = [
            (
                "id",
                "in",
                [self.config_id.currency_id.id, self.config_id.foreign_currency_id.id],
            )
        ]
        res["search_params"]["fields"].append("inverse_rate")
        return res

    def _loader_params_product_product(self):
        params = super()._loader_params_product_product()
        params["search_params"]["fields"].append("free_qty")
        params["search_params"]["fields"].append("qty_available")
        params["search_params"]["fields"].append("detailed_type")
        params["search_params"]["fields"].append("pos_sale_on_order")
        params["context"] = {
            **params["context"],
            "warehouse": self.config_id.picking_type_id.warehouse_id.id,
        }
        return params

    def _loader_params_res_country_city(self):
        return {"search_params": {"domain": [], "fields": ["name", "id"]}}

    def _get_pos_ui_res_country_city(self, params):
        return self.env["res.country.city"].search_read(**params["search_params"])

    def _pos_ui_models_to_load(self):
        result = super()._pos_ui_models_to_load()
        if "res.country.city" not in result:
            result.append("res.country.city")
        return result

    def get_pos_ui_product_product_by_params(self, custom_search_params):
        """
        :param custom_search_params: a dictionary containing params of a search_read()
        """
        params = self._loader_params_product_product()
        self = self.with_context(**params["context"])
        # custom_search_params will take priority
        params["search_params"] = {**params["search_params"], **custom_search_params}
        products = (
            self.env["product.product"]
            .with_context(active_test=False)
            .search_read(**params["search_params"])
        )
        products = self._sort_available_products(products)
        if len(products) > 0:
            self._process_pos_ui_product_product(products)
        return products

    def _sort_available_products(self, products):
        if not self.env.company.pos_show_just_products_with_available_qty:
            return products

        return sorted(products, key=lambda x: x["qty_available"], reverse=True)

    def _get_pos_ui_res_currency(self, params):
        """
        This method is used to get the res.currency for the pos
        is override to change the order of the currencies
        ------
        Return:
        Array:
            0: company currency
            1: foreign currency
        """
        res = self.env["res.currency"].search_read(**params["search_params"])
        if res[0]["id"] != self.config_id.currency_id.id:
            return [res[1], res[0]]
        return res

    def is_user_authorized(self):
        is_group = self.env.user.has_group("l10n_ve_pos.group_authorized_discount_pos")
        return is_group

    def _get_pos_ui_product_category(self, params):
        categories = self.env["product.category"].search_read(**params["search_params"])
        category_by_id = {category["id"]: category for category in categories}

        for category in categories:
            try:
                category["parent"] = (
                    category_by_id[category["parent_id"][0]]
                    if category["parent_id"]
                    else None
                )
            except KeyError as e:
                raise ValueError(
                    _("The category %s does not belong to this company.")
                    % category["parent_id"][1]
                ) from e

        return categories

    def _process_pos_ui_product_product(self, products):
        """
        Modify the list of products to add the categories as well as adapt the lst_price
        :param products: a list of products
        """
        if self.config_id.currency_id != self.company_id.currency_id:
            for product in products:
                product["lst_price"] = self.company_id.currency_id._convert(
                    product["lst_price"],
                    self.config_id.currency_id,
                    self.company_id,
                    fields.Date.today(),
                )

        categories = self._get_pos_ui_product_category(
            self._loader_params_product_category()
        )
        product_category_by_id = {category["id"]: category for category in categories}

        for product in products:
            categ_id = product["categ_id"][0]
            if categ_id in product_category_by_id:
                product["categ"] = product_category_by_id[categ_id]
            else:
                raise ValueError(
                    _("The category %s does not belong to this company.")
                    % product["categ_id"][1]
                )

            product["image_128"] = bool(product["image_128"])

    def _create_account_move(
        self,
        balancing_account=False,
        amount_to_balance=0,
        bank_payment_method_diffs=None,
    ):
        """
        This function was overwritten to assign the cash rate since it was previously assigned
        after creation.

        Additionally, the execution of the function: "compute_line_ids_foreign_debit_and_credit"
        is added so that it can calculate it
        """
        res = super()._create_account_move(
            balancing_account, amount_to_balance, bank_payment_method_diffs
        )
        account_move = self.move_id
        account_move.write(
            {
                "foreign_rate": self.config_id.foreign_rate,
                "foreign_inverse_rate": self.config_id.foreign_inverse_rate,
            }
        )
        return res

    def _accumulate_amounts(self, data):
        data = super()._accumulate_amounts(data)
        split_receivables_bank = data.get("split_receivables_bank")
        split_receivables_cash = data.get("split_receivables_cash")
        combine_receivables_bank = data.get("combine_receivables_bank")
        combine_receivables_cash = data.get("combine_receivables_cash")
        combine_invoice_receivables = data.get("combine_invoice_receivables")
        split_invoice_receivables = data.get("split_invoice_receivables")

        currency_rounding = self.currency_id.rounding
        for order in self.order_ids:
            order_is_invoiced = order.is_invoiced
            for payment in order.payment_ids:
                amount = payment.amount
                foreign_amount = payment.foreign_amount
                if float_is_zero(amount, precision_rounding=currency_rounding):
                    continue
                date = payment.payment_date
                payment_method = payment.payment_method_id
                is_split_payment = payment.payment_method_id.split_transactions
                payment_type = payment_method.type

                if payment_type != "pay_later":
                    if is_split_payment and payment_type == "cash":
                        split_receivables_cash[payment] = self._update_amounts(
                            split_receivables_cash[payment],
                            {"amount": 0, "foreign_amount": foreign_amount},
                            date,
                        )
                    elif not is_split_payment and payment_type == "cash":
                        combine_receivables_cash[payment_method] = self._update_amounts(
                            combine_receivables_cash[payment_method],
                            {"amount": 0, "foreign_amount": foreign_amount},
                            date,
                        )
                    elif is_split_payment and payment_type == "bank":
                        split_receivables_bank[payment] = self._update_amounts(
                            split_receivables_bank[payment],
                            {"amount": 0, "foreign_amount": foreign_amount},
                            date,
                        )
                    elif not is_split_payment and payment_type == "bank":
                        combine_receivables_bank[payment_method] = self._update_amounts(
                            combine_receivables_bank[payment_method],
                            {"amount": 0, "foreign_amount": foreign_amount},
                            date,
                        )

                    # Create the vals to create the pos receivables that will balance the pos receivables from invoice payment moves.
                    if order_is_invoiced:
                        if is_split_payment:
                            split_invoice_receivables[payment] = self._update_amounts(
                                split_invoice_receivables[payment],
                                {
                                    "amount": 0,
                                    "foreign_amount": payment.foreign_amount,
                                },
                                order.date_order,
                            )
                        else:
                            combine_invoice_receivables[payment_method] = (
                                self._update_amounts(
                                    combine_invoice_receivables[payment_method],
                                    {
                                        "amount": 0,
                                        "foreign_amount": payment.foreign_amount,
                                    },
                                    order.date_order,
                                )
                            )

        data.update(
            {
                "split_receivables_cash": split_receivables_cash,
                "combine_receivables_cash": combine_receivables_cash,
                "split_receivables_bank": split_receivables_bank,
                "combine_receivables_bank": combine_receivables_bank,
                "combine_invoice_receivables": combine_invoice_receivables,
                "split_invoice_receivables": split_invoice_receivables,
            }
        )
        return data

    def _update_amounts(
        self,
        old_amounts,
        amounts_to_add,
        date,
        round=True,
        force_company_currency=False,
    ):
        new_amounts = super()._update_amounts(
            old_amounts, amounts_to_add, date, round, force_company_currency
        )
        foreign_amount = amounts_to_add.get("foreign_amount", 0)
        new_amounts.update(
            {"foreign_amount": old_amounts.get("foreign_amount", 0) + foreign_amount}
        )
        return new_amounts

    def _create_invoice_receivable_lines(self, data):
        res = super()._create_invoice_receivable_lines(data)
        combine_invoice_receivable_lines = res.get("combine_invoice_receivable_lines")
        split_invoice_receivable_lines = res.get("split_invoice_receivable_lines")
        combine_invoice_receivables = res.get("combine_invoice_receivables")

        for payment_method, amounts in combine_invoice_receivables.items():
            line = combine_invoice_receivable_lines[payment_method]
            if line.credit > 0:
                line.not_foreign_recalculate = True
                line.foreign_credit = abs(amounts["foreign_amount"])
            if line.debit > 0:
                line.not_foreign_recalculate = True
                line.foreign_debit = abs(amounts["foreign_amount"])

        for payment in split_invoice_receivable_lines.keys():
            line = split_invoice_receivable_lines[payment]
            if line.credit > 0:
                line.not_foreign_recalculate = True
                line.foreign_credit = abs(payment["foreign_amount"])
            if line.debit > 0:
                line.not_foreign_recalculate = True
                line.foreign_debit = abs(payment["foreign_amount"])

        return res

    def _create_bank_payment_moves(self, data):
        res = super()._create_bank_payment_moves(data)
        payment_to_receivable_lines = res.get("payment_to_receivable_lines")
        payment_method_to_receivable_lines = res.get(
            "payment_method_to_receivable_lines"
        )
        combine_receivables_bank = data.get("combine_receivables_bank")

        for payment_method, amounts in combine_receivables_bank.items():
            lines = payment_method_to_receivable_lines[payment_method]
            for line in lines:
                if line.credit > 0:
                    line.not_foreign_recalculate = True
                    line.foreign_credit = abs(amounts["foreign_amount"])
                if line.debit > 0:
                    line.not_foreign_recalculate = True
                    line.foreign_debit = abs(amounts["foreign_amount"])

        for payment in payment_to_receivable_lines.keys():
            lines = payment_to_receivable_lines[payment]
            for line in lines:
                if line.credit > 0:
                    line.not_foreign_recalculate = True
                    line.foreign_credit = abs(payment["foreign_amount"])
                if line.debit > 0:
                    line.not_foreign_recalculate = True
                    line.foreign_debit = abs(payment["foreign_amount"])
        return res

    def _create_cash_statement_lines_and_cash_move_lines(self, data):
        res = super()._create_cash_statement_lines_and_cash_move_lines(data)
        split_receivables_cash = res.get("split_receivables_cash")
        combine_receivables_cash = res.get("combine_receivables_cash")
        split_cash_statement_lines = res.get("split_cash_statement_lines")
        combine_cash_statement_lines = res.get("combine_cash_statement_lines")
        split_cash_receivable_lines = res.get("split_cash_receivable_lines")
        combine_cash_receivable_lines = res.get("combine_cash_receivable_lines")

        for payment, amounts in split_receivables_cash.items():
            lines = split_cash_receivable_lines + split_cash_statement_lines
            for line in lines:
                self.set_foreign_amount_in_line(
                    line, amounts["foreign_amount"], amounts["amount"]
                )

        for payment_method, amounts in combine_receivables_cash.items():
            lines = combine_cash_receivable_lines + combine_cash_statement_lines
            for line in lines:
                self.set_foreign_amount_in_line(
                    line, amounts["foreign_amount"], amounts["amount"]
                )
        return data

    def set_foreign_amount_in_line(self, line, foreign_amount, amount=0.0):
        other_lines = line.move_id.line_ids.filtered(
            lambda x: x != line and x.account_id.account_type != "asset_receivable"
        )
        if other_lines:
            other_line = other_lines[0]
            if (
                abs(line.credit) > 0
                and float_compare(
                    line.credit,
                    abs(amount),
                    precision_rounding=self.currency_id.rounding,
                )
                == 0
            ):
                line.not_foreign_recalculate = True
                line.foreign_credit = abs(foreign_amount)
                if other_line.foreign_debit != line.foreign_credit:
                    other_line.foreign_debit = abs(line.foreign_credit)
            if (
                abs(line.debit) > 0
                and float_compare(
                    line.debit,
                    abs(amount),
                    precision_rounding=self.currency_id.rounding,
                )
                == 0
            ):
                line.not_foreign_recalculate = True
                line.foreign_debit = abs(foreign_amount)
                if other_line.foreign_credit != line.foreign_debit:
                    other_line.foreign_credit = abs(line.foreign_debit)

    def _validate_cross_move(self):
        """This function validate cross move, the proposal of this function is the transitory account be zero"""
        for session in self:
            cross_move_data = {}
            for order_payment in session.order_ids.payment_ids:
                payment_method = order_payment.payment_method_id

                if (
                    payment_method.apply_one_cross_move
                    and not payment_method.split_transactions
                ):

                    if payment_method not in cross_move_data:
                        cross_move_data[payment_method] = {
                            "amount": 0.0,
                            "foreign_amount": 0.0,
                            "partner_id": order_payment.partner_id.id,
                            "foreign_rate": order_payment.foreign_rate,
                            "foreign_currency_id": order_payment.foreign_currency_id.id,
                        }

                    cross_move_data[payment_method]["amount"] += order_payment.amount
                    cross_move_data[payment_method][
                        "foreign_amount"
                    ] += order_payment.foreign_amount

            for payment_method, amounts in cross_move_data.items():

                if float_is_zero(
                    amounts["amount"], precision_rounding=self.currency_id.rounding
                ):
                    continue

                if (
                    payment_method.cross_account_journal
                    and payment_method.cross_journal
                ):
                    if amounts["amount"] < 0:
                        line_vals = session._line_vals_move_cross_outgoing_aggregated(
                            payment_method, amounts
                        )
                    else:
                        line_vals = session._line_vals_move_cross_incoming_aggregated(
                            payment_method, amounts
                        )

                    session._create_cross_move_aggregated(
                        payment_method, line_vals, amounts
                    )

    def action_pos_session_close(
        self,
        balancing_account=False,
        amount_to_balance=0,
        bank_payment_method_diffs=None,
    ):
        """
        When the session is closed, the cross move is created.
        """
        res = super().action_pos_session_close(
            balancing_account, amount_to_balance, bank_payment_method_diffs
        )
        for session in self:
            session._validate_cross_move()
        return res

    def _create_combine_account_payment(self, payment_method, amounts, diff_amount):
        res = super(
            PosSession, self.with_context(from_pos=True)
        )._create_combine_account_payment(payment_method, amounts, diff_amount)
        account_payment = res.move_id.payment_id
        account_payment.with_context(skip_account_move_synchronization=True).write(
            {
                "foreign_rate": self.config_id.foreign_rate,
                "foreign_inverse_rate": self.config_id.foreign_inverse_rate,
            }
        )

        for line in account_payment.move_id.line_ids:
            if line.credit > 0 and amounts.get("foreign_amount", False):
                line.not_foreign_recalculate = True
                line.foreign_credit = abs(amounts["foreign_amount"])

            if line.debit > 0 and amounts.get("foreign_amount", False):
                line.not_foreign_recalculate = True
                line.foreign_debit = abs(amounts["foreign_amount"])
        if account_payment.pos_payment_method_id.split_transactions:
            self._create_cross_move_payment(res)
        return res

    def _create_split_account_payment(self, payment, amounts):
        res = super(
            PosSession, self.with_context(from_pos=True)
        )._create_split_account_payment(payment, amounts)
        account_payment = res.move_id.payment_id
        account_payment.with_context(skip_account_move_synchronization=True).write(
            {
                "foreign_rate": self.config_id.foreign_rate,
                "foreign_inverse_rate": self.config_id.foreign_inverse_rate,
            }
        )

        for line in account_payment.move_id.line_ids:
            if line.credit > 0:
                line.not_foreign_recalculate = True
                line.foreign_credit = abs(payment.foreign_amount)

            if line.debit > 0:
                line.not_foreign_recalculate = True
                line.foreign_debit = abs(payment.foreign_amount)
        if account_payment.pos_payment_method_id.split_transactions:
            self._create_cross_move_payment(res, amounts)
        return res

    def _create_cross_move_payment(self, move, amounts):
        account_payment = move.move_id.payment_id

        partner_id = (
            account_payment.partner_id.id if account_payment.partner_id else False
        )

        move_name_value = (
            account_payment.pos_order_id.name
            if account_payment.pos_order_id
            else account_payment.name
        )
        line_ids = []
        if amounts.get("amount", 0) > 0:
            line_ids = self._line_vals_move_cross_payment_incoming(move, amounts)
        else:
            line_ids = self._line_vals_move_cross_payment_outgoing(move, amounts)
        move_ref_value = _("Cross Move per Operation - Session: %s") % self.name
        move = self.env["account.move"].create(
            {
                "name": move_name_value,
                "date": move.move_id.create_date,
                "journal_id": move.move_id.payment_id.pos_payment_method_id.cross_account_journal.id,
                "state": "draft",
                "line_ids": line_ids,
                "foreign_currency_id": move.move_id.foreign_currency_id.id,
                "foreign_rate": move.move_id.foreign_rate,
                "partner_id": partner_id,
                "ref": move_ref_value,
                "company_id": self.company_id.id,
                **(
                    {
                        "account_analytic_id": (
                            (
                                getattr(self, "sh_analytic_account", False)
                                or getattr(self.config_id, "sh_analytic_account", False)
                            ).id
                        )
                    }
                    if (
                        getattr(self, "sh_analytic_account", False)
                        or getattr(self.config_id, "sh_analytic_account", False)
                    )
                    else {}
                ),
                "is_pos_cross_move": True,
            }
        )
        return move

    def _create_cross_move_aggregated(self, payment_method, line_vals, amounts):
        """
         This method create the move for the transitory account sets zero, using aggregated data.

        Args:
            payment_method (pos.payment.method): payment method object
            line_vals (account.move.line): move line to move cross
            amounts (dict): aggregated amounts

        Returns:
            account.move: Pos payment method adjustment move.
        """

        foreign_currency_id = amounts["foreign_currency_id"]
        foreign_rate = amounts["foreign_rate"]

        move_name_value = self.name
        move_ref_value = _("Unique PoS Cross Move - Sesión: %s") % self.name

        move = self.env["account.move"].create(
            {
                "name": move_name_value,
                "ref": move_ref_value,
                "date": fields.Date.today(),
                "journal_id": payment_method.cross_account_journal.id,
                "state": "draft",
                "line_ids": line_vals,
                "foreign_currency_id": foreign_currency_id,
                "foreign_rate": foreign_rate,
                "company_id": self.company_id.id,
                **(
                    {
                        "account_analytic_id": (
                            (
                                getattr(self, "sh_analytic_account", False)
                                or getattr(self.config_id, "sh_analytic_account", False)
                            ).id
                        )
                    }
                    if (
                        getattr(self, "sh_analytic_account", False)
                        or getattr(self.config_id, "sh_analytic_account", False)
                    )
                    else {}
                ),
                "is_pos_cross_move": True,
            }
        )
        return move
        # METHODS OF THE account.move.line #
    
    def _line_vals_move_cross_incoming_aggregated(self, payment_method, amounts):
        """
        Creates move_lines for the aggregated cross move when payment is incoming.

        Args:
            payment_method (pos.payment.method): payment method object
            amounts (dict): aggregated amounts {'amount': X, 'foreign_amount': Y, ...}

        Returns:
            list: move line commands
        """
        credit_account = 0
        debit_account = 0
        move_lines = []

        debit_account = (
            payment_method.outstanding_account_id.id
            if payment_method.type == "bank"
            else payment_method.cross_journal.suspense_account_id.id
        )
        for account_method in payment_method.cross_journal:
            credit_account = (
                account_method.inbound_payment_method_line_ids.payment_account_id.id
            )
            currency = (
                account_method.currency_id.id
                if account_method.currency_id
                else self.env.company.currency_id.id
            )

            total_amount = amounts["amount"]
            total_foreign_amount = amounts["foreign_amount"]
            partner_id = amounts["partner_id"]
            foreign_rate = amounts["foreign_rate"]

            move_lines.extend(
                [
                    Command.create(
                        {
                            "name": _("PoS Payment Method Adjustment"),
                            "account_id": credit_account,
                            "amount_currency": (
                                total_amount
                                if currency == self.env.company.currency_id.id
                                else total_foreign_amount
                            ),
                            "credit": 0.0,
                            "foreign_credit": 0.0,
                            "debit": total_amount,
                            "foreign_debit": total_foreign_amount,
                            "not_foreign_recalculate": True,
                            "foreign_rate": foreign_rate,
                            "currency_id": currency,
                        }
                    ),
                    Command.create(
                        {
                            "name": _("PoS Payment Method Adjustment"),
                            "account_id": debit_account,
                            "amount_currency": (
                                -total_amount
                                if currency == self.env.company.currency_id.id
                                else -total_foreign_amount
                            ),
                            "debit": 0.0,
                            "foreign_debit": 0.0,
                            "credit": total_amount,
                            "foreign_credit": total_foreign_amount,
                            "not_foreign_recalculate": True,
                            "foreign_rate": foreign_rate,
                            "currency_id": currency,
                        }
                    ),
                ]
            )
            return move_lines

    def _line_vals_move_cross_outgoing_aggregated(self, payment_method, amounts):
        """
        Creates move_lines for the aggregated cross move when payment is outgoing (is change).

        Args:
            payment_method (pos.payment.method): payment method object
            amounts (dict): aggregated amounts {'amount': X, 'foreign_amount': Y, ...}

        Returns:
            list: move line commands
        """
        credit_account = 0
        debit_account = 0
        move_lines = []

        debit_account = payment_method.outstanding_account_id.id

        for account_method in payment_method.cross_journal:
            credit_account = (
                account_method.outbound_payment_method_line_ids.payment_account_id.id
            )
            currency = (
                account_method.currency_id.id
                if account_method.currency_id
                else self.env.company.currency_id.id
            )

            total_amount = abs(amounts["amount"])
            total_foreign_amount = abs(amounts["foreign_amount"])
            partner_id = amounts["partner_id"]
            foreign_rate = amounts["foreign_rate"]

            original_amount = amounts["amount"]
            original_foreign_amount = amounts["foreign_amount"]
            move_lines.extend(
                [
                    Command.create(
                        {
                            "name": _("PoS Payment Method Adjustment"),
                            "account_id": debit_account,
                            "amount_currency": (
                                total_amount
                                if currency == self.env.company.currency_id.id
                                else total_foreign_amount
                            ),
                            "credit": 0.0,
                            "foreign_credit": 0.0,
                            "debit": total_amount,
                            "foreign_debit": total_foreign_amount,
                            "not_foreign_recalculate": True,
                            "foreign_rate": foreign_rate,
                            "currency_id": currency,
                        }
                    ),
                    Command.create(
                        {
                            "name": _("PoS Payment Method Adjustment"),
                            "account_id": credit_account,
                            "amount_currency": (
                                original_amount
                                if currency == self.env.company.currency_id.id
                                else original_foreign_amount
                            ),
                            "debit": 0.0,
                            "foreign_debit": 0.0,
                            "credit": total_amount,
                            "foreign_credit": total_foreign_amount,
                            "not_foreign_recalculate": True,
                            "foreign_rate": foreign_rate,
                            "currency_id": currency,
                        }
                    ),
                ]
            )

            return move_lines
    
    def _line_vals_move_cross_payment_incoming(self, move, amounts):
        """
        This method creates the move_lines for the move_cross when the payment is incoming(Sale Payment).

        Args:
            payment (account.payment): payment generate from PoS

        Returns:
            account.move.line: move line to move cross
        """

        credit_account = 0
        debit_account = 0
        move_lines = []
        payment_method = move.move_id.payment_id.pos_payment_method_id
        debit_account = payment_method.outstanding_account_id.id

        for (
            account_method
        ) in payment_method.cross_journal:
            credit_account = (
                account_method.inbound_payment_method_line_ids.payment_account_id.id
            )
            currency = (
                account_method.currency_id.id
                if account_method.currency_id
                else self.env.company.currency_id.id
            )
            total_amount = amounts["amount"]
            total_foreign_amount = amounts["foreign_amount"]
            foreign_rate = amounts.get("foreign_rate", move.move_id.payment_id.foreign_rate)
            
            move_lines.extend(
                [
                    Command.create(
                        {
                            "name": _("PoS Payment Method Adjustment"),
                            "account_id": credit_account,
                            "amount_currency": (
                                total_amount
                                if currency == self.env.company.currency_id.id
                                else total_foreign_amount
                            ),
                            "credit": 0.0,
                            "foreign_credit": 0.0,
                            "debit": total_amount,
                            "foreign_debit": total_foreign_amount,
                            "not_foreign_recalculate": True,
                            "foreign_rate": foreign_rate,
                            "currency_id": currency,
                        }
                    ),
                    Command.create(
                        {
                            "name": _("PoS Payment Method Adjustment"),
                            "account_id": debit_account,
                            "amount_currency": (
                                -total_amount
                                if currency == self.env.company.currency_id.id
                                else -total_foreign_amount
                            ),
                            "debit": 0.0,
                            "foreign_debit": 0.0,
                            "credit": total_amount,
                            "foreign_credit": total_foreign_amount,
                            "not_foreign_recalculate": True,
                            "foreign_rate": foreign_rate,
                            "currency_id": currency,
                        }
                    ),
                ]
            )

            return move_lines

    def _line_vals_move_cross_payment_outgoing(self, move, amounts):
        """
        This method creates the move_lines for the move_cross when the payment is outgoing(Refund Payment).

        Args:
            payment (account.payment): payment generate from PoS

        Returns:
            account.move.line: move line to move cross
        """
        credit_account = 0
        debit_account = 0
        move_lines = []
        for account in move.move_id.payment_id.pos_payment_method_id:
            debit_account = account.outstanding_account_id.id

        for (
            account_method
        ) in move.move_id.payment_id.pos_payment_method_id.cross_journal:
            credit_account = (
                account_method.outbound_payment_method_line_ids.payment_account_id.id
            )
            currency = (
                account_method.currency_id.id
                if account_method.currency_id
                else self.env.company.currency_id.id
            )
            total_amount = abs(amounts["amount"])
            total_foreign_amount = abs(amounts["foreign_amount"])
            foreign_rate = amounts.get("foreign_rate", move.move_id.payment_id.foreign_rate)

            original_amount = amounts["amount"]
            original_foreign_amount = amounts["foreign_amount"]
            
            move_lines.extend(
                [
                    Command.create(
                        {
                            "name": _("PoS Payment Method Adjustment"),
                            "account_id": debit_account,
                            "amount_currency": (
                                total_amount
                                if currency == self.env.company.currency_id.id
                                else total_foreign_amount
                            ),
                            "credit": 0.0,
                            "foreign_credit": 0.0,
                            "debit": total_amount,
                            "foreign_debit": total_foreign_amount,
                            "not_foreign_recalculate": True,
                            "foreign_rate": foreign_rate,
                            "currency_id": currency,
                        }
                    ),
                    Command.create(
                        {
                            "name": _("PoS Payment Method Adjustment"),
                            "account_id": credit_account,
                            "amount_currency": (
                                original_amount
                                if currency == self.env.company.currency_id.id
                                else original_foreign_amount
                            ),
                            "debit": 0.0,
                            "foreign_debit": 0.0,
                            "credit": total_amount,
                            "foreign_credit": total_foreign_amount,
                            "not_foreign_recalculate": True,
                            "foreign_rate": foreign_rate,
                            "currency_id": currency,
                        }
                    ),
                ]
            )

            return move_lines
