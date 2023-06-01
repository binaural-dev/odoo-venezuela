from odoo import models, fields, api


class PosSession(models.Model):
    _inherit = "pos.session"

    def load_pos_data(self):
        res = super().load_pos_data()
        res["prefix_vats"] = self.env["res.partner"]._fields["prefix_vat"].selection
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
        return params

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
