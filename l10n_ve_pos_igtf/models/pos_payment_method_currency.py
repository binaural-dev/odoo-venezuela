from odoo import api, fields, models


class PosPaymentMethodCurrency(models.Model):
    _inherit = "pos.payment.method.currency"

    apply_igtf = fields.Boolean(
        string="Apply IGTF",
        default=False,
        help="The payments made in this currency with this payment method "
        "generate IGTF.",
    )

    @api.model
    def _load_pos_data_fields(self, config):
        res = super()._load_pos_data_fields(config)
        res.append("apply_igtf")
        return res
