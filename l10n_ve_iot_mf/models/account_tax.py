from odoo import models, fields, api


class AccountTaxInherit(models.Model):
    _inherit = "account.tax"

    fiscal_code = fields.Integer(default=0)

    @api.model
    def _load_pos_data_fields(self, config_id):
        fields_to_load = super()._load_pos_data_fields(config_id)
        if "fiscal_code" not in fields_to_load:
            fields_to_load.append("fiscal_code")
        return fields_to_load
