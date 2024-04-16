from odoo import models, fields, api, _, Command
from odoo.tools import float_is_zero, float_compare
from odoo.osv.expression import AND, OR


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

    def _create_combine_account_payment(self, payment_method, amounts, diff_amount):
        # OVERWRITE
        # Inside this method the payment session is created, here set de foreign_rate because lines dont have foreign debit and credit
        outstanding_account = (
            payment_method.outstanding_account_id
            or self.company_id.account_journal_payment_debit_account_id
        )
        destination_account = self._get_receivable_account(payment_method)

        if float_compare(amounts["amount"], 0, precision_rounding=self.currency_id.rounding) < 0:
            # revert the accounts because account.payment doesn't accept negative amount.
            outstanding_account, destination_account = destination_account, outstanding_account

        account_payment = self.env["account.payment"].create(
            {
                "amount": abs(amounts["amount"]),
                "journal_id": payment_method.journal_id.id,
                "foreign_rate": self.config_id.foreign_rate,
                "foreign_inverse_rate": self.config_id.foreign_inverse_rate,
                "force_outstanding_account_id": outstanding_account.id,
                "destination_account_id": destination_account.id,
                "ref": _("Combine %s POS payments from %s") % (payment_method.name, self.name),
                "pos_payment_method_id": payment_method.id,
                "pos_session_id": self.id,
            }
        )

        diff_amount_compare_to_zero = self.currency_id.compare_amounts(diff_amount, 0)
        if diff_amount_compare_to_zero != 0:
            self._apply_diff_on_account_payment_move(account_payment, payment_method, diff_amount)

        account_payment.action_post()
        return account_payment.move_id.line_ids.filtered(
            lambda line: line.account_id == account_payment.destination_account_id
        )

    def _create_split_account_payment(self, payment, amounts):
        # OVERWRITE
        # Inside this method the payment session is created, here set de foreign_rate because lines dont have foreign debit and credit
        payment_method = payment.payment_method_id
        if not payment_method.journal_id:
            return self.env["account.move.line"]
        outstanding_account = (
            payment_method.outstanding_account_id
            or self.company_id.account_journal_payment_debit_account_id
        )
        accounting_partner = self.env["res.partner"]._find_accounting_partner(payment.partner_id)
        destination_account = accounting_partner.property_account_receivable_id

        if float_compare(amounts["amount"], 0, precision_rounding=self.currency_id.rounding) < 0:
            # revert the accounts because account.payment doesn't accept negative amount.
            outstanding_account, destination_account = destination_account, outstanding_account

        account_payment = self.env["account.payment"].create(
            {
                "amount": abs(amounts["amount"]),
                "partner_id": payment.partner_id.id,
                "journal_id": payment_method.journal_id.id,
                "foreign_rate": payment.foreign_rate,
                "foreign_inverse_rate": payment.foreign_rate,
                "force_outstanding_account_id": outstanding_account.id,
                "destination_account_id": destination_account.id,
                "ref": _("%s POS payment of %s in %s")
                % (payment_method.name, payment.partner_id.display_name, self.name),
                "pos_payment_method_id": payment_method.id,
                "pos_session_id": self.id,
            }
        )
        account_payment.action_post()

        return account_payment.move_id.line_ids.filtered(
            lambda line: line.account_id == account_payment.destination_account_id
        )

    def _create_account_move(
        self, balancing_account=False, amount_to_balance=0, bank_payment_method_diffs=None
    ):
        """
        This function was overwritten to assign the cash rate since it was previously assigned
        after creation.

        Additionally, the execution of the function: "compute_line_ids_foreign_debit_and_credit"
        is added so that it can calculate it
        """
        account_move = self.env["account.move"].create(
            {
                "journal_id": self.config_id.journal_id.id,
                "date": fields.Date.context_today(self),
                # >> Binaural
                "foreign_rate": self.config_id.foreign_rate,
                "foreign_inverse_rate": self.config_id.foreign_inverse_rate,
                # << Binaural
                "ref": self.name,
            }
        )
        self.write({"move_id": account_move.id})

        data = {"bank_payment_method_diffs": bank_payment_method_diffs or {}}
        data = self._accumulate_amounts(data)
        data = self._create_non_reconciliable_move_lines(data)
        data = self._create_bank_payment_moves(data)
        data = self._create_pay_later_receivable_lines(data)
        data = self._create_cash_statement_lines_and_cash_move_lines(data)
        data = self._create_invoice_receivable_lines(data)
        data = self._create_stock_output_lines(data)
        if balancing_account and amount_to_balance:
            data = self._create_balancing_line(data, balancing_account, amount_to_balance)

        # >> Binaural
        account_move.compute_line_ids_foreign_debit_and_credit()
        # << Binaural
        return data


    def _validate_cross_move(self):
        """This function validate cross move, the proposal of this function is the transitory account be zero"""

        for session in self:
            for payment in session:
                for order in payment.order_ids:
                    for order_payment in order.payment_ids:
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
                        "debit": 0.0,
                        "foreign_rate": payment.foreign_rate,
                    }
                ),
                Command.create(
                    {
                        "name": _("PoS Payment Method Adjustment"),
                        "account_id": debit_account,
                        "partner_id": payment.partner_id.id,
                        "debit": payment.amount,
                        "credit": 0.0,
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
                        "debit": payment.amount,
                        "foreign_rate": payment.foreign_rate,
                    }
                ),
                Command.create(
                    {
                        "name": _("PoS Payment Method Adjustment"),
                        "account_id": credit_account,
                        "partner_id": payment.partner_id.id,
                        "debit": 0.0,
                        "credit": payment.amount,
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
