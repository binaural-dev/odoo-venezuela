from odoo import models, fields, api, _
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

        products = self._filter_products(products)
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
        products = self._filter_products(products)
        if len(products) > 0:
            self._process_pos_ui_product_product(products)
        return products

    def _filter_products(self, products):
        if not self.env.company.pos_show_just_products_with_available_qty:
            return products

        filter_products = []
        for product in products:
            if product["qty_available"] > 0:
                filter_products.append(product)

        return filter_products

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
        return self.env.user.authorized_discount_pos

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
