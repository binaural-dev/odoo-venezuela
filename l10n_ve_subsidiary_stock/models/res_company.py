from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"
    
    def _get_queries_to_set_subsidiary(self):
        res = super()._get_queries_to_set_subsidiary()
        res.append(
            "UPDATE stock_valuation_layer SET subsidiary_id = %s WHERE subsidiary_id IS NULL AND company_id = %s",
        )
        res.append(
            "UPDATE stock_warehouse SET subsidiary_id = %s WHERE subsidiary_id IS NULL AND company_id = %s",
        )
        return res
