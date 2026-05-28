from odoo import api, fields, models


class PosPaymentMethod(models.Model):
    _inherit = "pos.payment.method"

    apply_igtf = fields.Boolean(default=False)

    @api.model
    def _load_pos_data_fields(self, config_id):
        fields_to_load = super()._load_pos_data_fields(config_id)
        if "apply_igtf" not in fields_to_load:
            fields_to_load.append("apply_igtf")
        return fields_to_load
