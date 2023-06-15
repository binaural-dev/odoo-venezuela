from odoo import api, fields, models


class PosPayment(models.Model):
    _inherit = "pos.payment"

    foreign_rate = fields.Float(
        help="The rate that is gonna be always shown to the user.",
        default=0.0,
        readonly=False,
    )
    foreign_amount = fields.Float(readonly=True, digits=(16, 2))

    def _export_for_ui(self, payment):
        res = super()._export_for_ui(payment)
        res["foreign_rate"] = payment.foreign_rate
        res["foreign_amount"] = payment.foreign_amount
        return res

