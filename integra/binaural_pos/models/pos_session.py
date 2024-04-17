from odoo import models, fields, api, _, Command
from odoo.tools import float_is_zero, float_compare


class PosSession(models.Model):
    _inherit = "pos.session"

    def load_pos_data(self):
        res = super().load_pos_data()
        res["prefix_vats"] = self.env["res.partner"]._fields["prefix_vat"].selection
        return res

    def _loader_params_pos_payment(self):
        res = super()._loader_params_pos_payment(self)
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
        return res

    def _loader_params_res_currency(self):
        """
        This method is used to get the params for the search_read of res.currency
        """
        res = super()._loader_params_res_currency()
        res["search_params"]["domain"] = [
            ("id", "in", [self.config_id.currency_id.id, self.config_id.foreign_currency_id.id])
        ]
        res["search_params"]["fields"].append("inverse_rate")
        return res

    def _loader_params_product_product(self):
        params = super()._loader_params_product_product()
        params["search_params"]["fields"].append("free_qty")
        params["search_params"]["fields"].append("qty_available")
        params["search_params"]["fields"].append("detailed_type")
        return params

    def _get_pos_ui_product_product(self, params):
        self = self.with_context(**params["context"])
        products = []
        if not self.config_id.limited_products_loading:
            products = self.env["product.product"].search_read(**params["search_params"])
        else:
            products = self.config_id.get_limited_products_loading(
                params["search_params"]["fields"]
            )

        products = self._sort_available_products(products)
        self._process_pos_ui_product_product(products)
        return products

    def get_pos_ui_product_product_by_params(self, custom_search_params):
        """
        :param custom_search_params: a dictionary containing params of a search_read()
        """
        params = self._loader_params_product_product()
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
        is_group = self.env.user.has_group("binaural_pos.group_authorized_discount_pos")
        return is_group

    def _validate_cross_move(self):
        """This function validate cross move, the proposal of this function is the transitory account be zero"""
        for session in self:
            for order_payment in session.order_ids.payment_ids:
                if (
                    order_payment.payment_method_id.cross_account_journal
                    and order_payment.payment_method_id.cross_journal
                ):
                    if order_payment.amount < 0:
                        line_vals = session._line_vals_move_cross_outgoing(order_payment)
                    else:
                        line_vals = session._line_vals_move_cross_incoming(order_payment)

                        session._create_cross_move(order_payment, line_vals)

    def _line_vals_move_cross_incoming(self, payment):
        """
        This method creates the move_lines for the move_cross when the payment is incoming.

        Args:
            payment (account.payment): payment generate from PoS

        Returns:
            account.move.line: move line to move cross
        """
        credit_account = 0
        debit_account = 0
        for account in payment.payment_method_id:
            credit_account = account.outstanding_account_id.id

        for account in payment.payment_method_id.cross_journal:
            debit_account = account.inbound_payment_method_line_ids.payment_account_id.id

            
            return [
                Command.create(
                    {
                        "name": _("PoS Payment Method Adjustment"),
                        "account_id": credit_account,
                        "partner_id": payment.partner_id.id,
                        "credit": payment.amount,
                        "foreign_credit": payment.foreign_amount,
                        "debit": 0.0,
                        "foreign_debit": 0.0,
                        "not_foreign_recalculate": True,
                        "foreign_rate": payment.foreign_rate,
                    }
                ),
                Command.create(
                    {
                        "name": _("PoS Payment Method Adjustment"),
                        "account_id": debit_account,
                        "partner_id": payment.partner_id.id,
                        "debit": payment.amount,
                        "foreign_debit": payment.foreign_amount,
                        "credit": 0.0,
                        "foreign_credit": 0.0,
                        "not_foreign_recalculate": True,
                        "foreign_rate": payment.foreign_rate,
                    }
                ),
            ]

    def _line_vals_move_cross_outgoing(self, payment):
        """
        This method creates the move_lines for the move_cross when the payment is outgoing (is change).

        Args:
            payment (pos.payment): payment generate from PoS

        Returns:
            account.move.line: move line to move cross
        """
        credit_account = 0
        debit_account = 0
        for account in payment.payment_method_id:
            debit_account = account.outstanding_account_id.id

        for account in payment.payment_method_id.cross_journal:
            credit_account = account.outbound_payment_method_line_ids.payment_account_id.id

            return [
                Command.create(
                    {
                        "name": _("PoS Payment Method Adjustment"),
                        "account_id": debit_account,
                        "partner_id": payment.partner_id.id,
                        "credit": 0.0,
                        "foreign_credit": 0.0,
                        "debit": payment.amount,
                        "foreign_debit": payment.foreign_amount,
                        "not_foreign_recalculate": True,
                        "foreign_rate": payment.foreign_rate,
                    }
                ),
                Command.create(
                    {
                        "name": _("PoS Payment Method Adjustment"),
                        "account_id": credit_account,
                        "partner_id": payment.partner_id.id,
                        "debit": 0.0,
                        "foreign_debit": 0.0,
                        "credit": payment.amount,
                        "foreign_credit": payment.foreign_amount,
                        "not_foreign_recalculate": True,
                        "foreign_rate": payment.foreign_rate,
                    }
                ),
            ]

    def _create_cross_move(self, payment, line_vals):
        """
         This method create the move for the transitory account sets zero.

        Args:
            payment (pos.payment): payment from PoS
            line_vals (account.move.line): move line to move cross

        Returns:
            account.move: Pos payment method adjustment move.
        """
        move = self.env["account.move"].create(
            {
                "name": _("PoS Payment Method Adjustment"),
                "date": payment.create_date,
                "journal_id": payment.payment_method_id.cross_account_journal.id,
                "state": "draft",
                "line_ids": line_vals,
                "foreign_currency_id": payment.foreign_currency_id.id,
                "foreign_rate": payment.foreign_rate,
                "company_id": self.company_id.id,
            }
        )
        return move

    def action_pos_session_close(
        self, balancing_account=False, amount_to_balance=0, bank_payment_method_diffs=None
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
        res = super()._create_combine_account_payment(payment_method, amounts, diff_amount)
        account_payment = res.move_id.payment_id
        account_payment.write(
            {
                "foreign_rate": self.config_id.foreign_rate,
                "foreign_inverse_rate": self.config_id.foreign_inverse_rate,
            }
        )

        for line in account_payment.move_id.line_ids:
            if line.credit > 0 and amounts.get("foreign_amount", False):
                line.not_foreign_recalculate = True
                line.foreign_credit = amounts["foreign_amount"]

            if line.debit > 0 and amounts.get("foreign_amount", False):
                line.not_foreign_recalculate = True
                line.foreign_debit = amounts["foreign_amount"]

        return res

    def _create_split_account_payment(self, payment, amounts):
        res = super()._create_split_account_payment(payment, amounts)
        account_payment = res.move_id.payment_id

        account_payment.write(
            {
                "foreign_rate": self.config_id.foreign_rate,
                "foreign_inverse_rate": self.config_id.foreign_inverse_rate,
            }
        )

        for line in account_payment.move_id.line_ids:
            if line.credit > 0:
                line.not_foreign_recalculate = True
                line.foreign_credit = payment.foreign_amount

            if line.debit > 0:
                line.not_foreign_recalculate = True
                line.foreign_debit = payment.foreign_amount

        return res

    def _create_account_move(
        self, balancing_account=False, amount_to_balance=0, bank_payment_method_diffs=None
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
        account_move.compute_line_ids_foreign_debit_and_credit()
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
                            combine_invoice_receivables[payment_method] = self._update_amounts(
                                combine_invoice_receivables[payment_method],
                                {
                                    "amount": 0,
                                    "foreign_amount": payment.foreign_amount,
                                },
                                order.date_order,
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
        self, old_amounts, amounts_to_add, date, round=True, force_company_currency=False
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
        payment_method_to_receivable_lines = res.get("payment_method_to_receivable_lines")
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
                self.set_foreign_amount_in_line(line, amounts["foreign_amount"], amounts["amount"])

        for payment_method, amounts in combine_receivables_cash.items():
            lines = combine_cash_receivable_lines + combine_cash_statement_lines
            for line in lines:
                self.set_foreign_amount_in_line(line, amounts["foreign_amount"], amounts["amount"])
        return data

    def set_foreign_amount_in_line(self, line, foreign_amount, amount=0.0):
        other_line = line.move_id.line_ids.filtered(
            lambda x: x != line and x.account_id.account_type != "asset_receivable"
        )
        if (
            abs(line.credit) > 0
            and float_compare(
                line.credit, abs(amount), precision_rounding=self.currency_id.rounding
            )
            == 0
        ):
            line.not_foreign_recalculate = True
            line.foreign_credit = abs(foreign_amount)
            if other_line and other_line.foreign_debit != line.foreign_credit:
                other_line.foreign_debit = line.foreign_credit
        if (
            abs(line.debit) > 0
            and float_compare(line.debit, abs(amount), precision_rounding=self.currency_id.rounding)
            == 0
        ):
            line.not_foreign_recalculate = True
            line.foreign_debit = abs(foreign_amount)
            if other_line and other_line.foreign_credit != line.foreign_debit:
                other_line.foreign_credit = line.foreign_debit
