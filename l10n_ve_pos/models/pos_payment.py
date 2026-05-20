from odoo import api, fields, models, _
from odoo.tools import float_is_zero, float_compare


import logging
_logger = logging.getLogger(__name__)


class PosPayment(models.Model):
    _inherit = "pos.payment"

    foreign_rate = fields.Float(
        help="The rate that is gonna be always shown to the user.",
        # default=0.0,
        readonly=False,
    )
    foreign_inverse_rate = fields.Float(
        help="Inverse rate used to compute foreign debit/credit on payment moves.",
        readonly=False,
    )
    foreign_amount = fields.Float(readonly=True, digits=(16, 2))
    foreign_currency_id = fields.Many2one("res.currency", compute="_compute_foreign_currency_id")

    @api.depends()
    def _compute_foreign_currency_id(self):
        for record in self:
            record.foreign_currency_id = record.env.company.foreign_currency_id

    def _export_for_ui(self, payment):
        res = super()._export_for_ui(payment)
        res["foreign_rate"] = payment.foreign_rate
        res["foreign_inverse_rate"] = payment.foreign_inverse_rate
        res["foreign_amount"] = payment.foreign_amount
        return res

    def _get_payment_rate_values(self, payment):
        order = payment.pos_order_id
        config = order.config_id if order else self.env["pos.config"]
        rate = payment.foreign_rate or config.foreign_rate or 0.0
        inverse_rate = payment.foreign_inverse_rate or config.foreign_inverse_rate or 0.0

        if not inverse_rate and rate:
            inverse_rate = 1 / rate
        if not rate and inverse_rate:
            rate = 1 / inverse_rate

        return rate, inverse_rate

    def _get_payment_foreign_amount(self, payment):
        company = self.env.company
        foreign_amount = company.currency_id._convert(
            payment.amount,
            company.foreign_currency_id,
            company,
            fields.Date.today()
        )

        return foreign_amount

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

            rate, inverse_rate = self._get_payment_rate_values(payment)
            foreign_amount = self._get_payment_foreign_amount(payment)

            

            payment_move.write(
                {
                    "foreign_rate": rate,
                    "foreign_inverse_rate": inverse_rate,
                    "manually_set_rate": True,
                }
            )
            for line in payment_move.line_ids:
                _logger.warning("Adding to move line %s the foreign amount %s", line.id, foreign_amount)
                vals = {"not_foreign_recalculate": True}
                if line.debit > 0:
                    vals["foreign_debit"] = abs(foreign_amount)
                    vals["foreign_credit"] = 0.0
                elif line.credit > 0:
                    vals["foreign_debit"] = 0.0
                    vals["foreign_credit"] = abs(foreign_amount)
                else:
                    vals["foreign_debit"] = 0.0
                    vals["foreign_credit"] = 0.0
                line.write(vals)
        return move_id
