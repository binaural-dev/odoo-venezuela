from odoo import fields, models, api


class PosPaymentMethod(models.Model):
    _inherit = "pos.payment.method"

    code_fiscal_printer = fields.Char(size=2, default="01")

    @api.model
    def _load_pos_data_fields(self, config_id):
        fields_to_load = super()._load_pos_data_fields(config_id)
        if "code_fiscal_printer" not in fields_to_load:
            fields_to_load.append("code_fiscal_printer")
        return fields_to_load
