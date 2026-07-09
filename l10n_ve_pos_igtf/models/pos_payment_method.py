from odoo import api, fields, models


class PosPaymentMethod(models.Model):
    _inherit = "pos.payment.method"

    apply_igtf = fields.Boolean(default=False)

    @api.model
    def _load_pos_data_fields(self, config):
        res = super()._load_pos_data_fields(config)
        res.append("apply_igtf")
        return res
