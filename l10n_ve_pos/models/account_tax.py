from odoo import api, models


class AccountTax(models.Model):
    _inherit = "account.tax"

    @api.model
    def _load_pos_data_fields(self, config):
        """Odoo 19 loader contract: extend the read with ``type_tax_use``
        so the Venezuelan POS can branch on the tax scope (sale/purchase/none).
        """
        res = super()._load_pos_data_fields(config)
        if "type_tax_use" not in res:
            res.append("type_tax_use")
        return res
