from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    use_subsidiary_with_multiple_municipalities = fields.Boolean()

    def _get_queries_to_set_subsidiary(self):
        res = super()._get_queries_to_set_subsidiary()
        res.append(
            "UPDATE account_retention SET account_analytic_id = %s WHERE account_analytic_id IS NULL AND company_id = %s",
        )
        res.append(
            "UPDATE account_retention_line SET account_analytic_id = %s WHERE account_analytic_id IS NULL AND company_id = %s",
        )
        return res
