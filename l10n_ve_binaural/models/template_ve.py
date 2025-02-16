# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models, _
from odoo.addons.account.models.chart_template import template


class AccountChartTemplate(models.AbstractModel):
    _inherit = "account.chart.template"

    @template("ve")
    def _get_ve_template_data(self):
        return {
            "code_digits": "7",
            "property_account_receivable_id": "account_activa_account_1122001",
            "property_account_payable_id": "account_activa_account_2122001",
            "property_account_expense_categ_id": "account_activa_account_7151001",
            "property_account_income_categ_id": "account_activa_account_5111001",
            "name": _("Venezuela - Binaural"),
        }

    @template("ve", "res.company")
    def _get_ve_res_company(self):
        return {
            self.env.company.id: {
                "account_fiscal_country_id": "base.ve",
                "bank_account_code_prefix": "1113",
                "cash_account_code_prefix": "1111",
                "transfer_account_code_prefix": "1129003",
                "account_default_pos_receivable_account_id": "account_activa_account_1122003",
                "income_currency_exchange_account_id": "account_activa_account_9212003",
                "expense_currency_exchange_account_id": "account_activa_account_9113006",
                "tax_calculation_rounding_method": "round_globally",
                "account_sale_tax_id": "tax1sale",
                "account_purchase_tax_id": "tax1purchase",
                "exempt_aliquot_sale": "tax0sale",
                "general_aliquot_sale": "tax1sale",
                "reduced_aliquot_sale": "tax2sale",
                "extend_aliquot_sale": "tax3sale",
                "exempt_aliquot_purchase": "tax0purchase",
                "general_aliquot_purchase": "tax1purchase",
                "reduced_aliquot_purchase": "tax2purchase",
                "extend_aliquot_purchase": "tax3purchase",
            },
        }
