from odoo import api, fields, models, _
from odoo.tools import float_is_zero, float_compare


import logging
_logger = logging.getLogger(__name__)


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

    def _create_payment_moves(self, is_reverse=False):
        """The function that creates the payment entry was overwritten so that it has the same
        rate as the invoice/order/payment
        """
        move_id = super()._create_payment_moves(is_reverse=is_reverse)
        for payment in self:
            payment_move = move_id.filtered(
                lambda x: float_compare(
                    abs(payment.amount),
                    x.amount_total,
                    precision_rounding=payment.pos_order_id.currency_id.rounding,
                )
                == 0
            )
            if not payment_move:
                continue

            payment_move.write(
                {
                    "foreign_rate": payment.foreign_rate,
                    "foreign_inverse_rate": payment.foreign_rate,
                    "manually_set_rate": True,
                }
            )
            for line in payment_move.line_ids:
                line.write(
                    {
                        "not_foreign_recalculate": True,
                        "foreign_debit": abs(payment.foreign_amount) if line.debit > 0 else 0,
                        "foreign_credit":  abs(payment.foreign_amount) if line.credit > 0 else 0,
                    }
                )
        return move_id
