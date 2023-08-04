from odoo import api, fields, models


class PosPayment(models.Model):
    _inherit = "pos.payment"

    foreign_rate = fields.Float(
        help="The rate that is gonna be always shown to the user.",
        default=0.0,
        readonly=False,
    )
    foreign_amount = fields.Float(readonly=True, digits=(16, 2))
    foreign_currency_id = fields.Many2one("res.currency", compute="_compute_foreign_currency_id")

    @api.depends()
    def _compute_foreign_currency_id(self):
        for record in self:
            record.foreign_currency_id = record.env.company.currency_foreign_id

    def _export_for_ui(self, payment):
        res = super()._export_for_ui(payment)
        res["foreign_rate"] = payment.foreign_rate
        res["foreign_amount"] = payment.foreign_amount
        return res

