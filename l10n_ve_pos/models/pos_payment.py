from odoo import api, fields, models
from odoo.tools import float_compare


class PosPayment(models.Model):
    _inherit = "pos.payment"

    # Odoo 19 frontend `PosPayment` expects these base fields when creating/
    # mutating payment lines (e.g. setAmount -> pos_order_id.assertEditable()).
    _POS_PAYMENT_CORE_FIELDS = (
        "id",
        "name",
        "uuid",
        "amount",
        "payment_date",
        "payment_method_id",
        "payment_status",
        "ticket",
        "is_change",
        "pos_order_id",
        "currency_id",
        # Required by core's DevicesSynchronisation.constructOrdersDomain,
        # which calls record.write_date.plus(...) on every dynamic model.
        "write_date",
    )

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
            record.foreign_currency_id = record.env.company.foreign_currency_id

    @api.model
    def _load_pos_data_fields(self, config):
        """Keep Odoo 19 core payment contract and extend it with Venezuelan
        foreign-currency fields.

        Important: `pos.load.mixin._load_pos_data_fields` returns `[]` for
        pos.payment in core, which is a special value meaning "load every
        field" (see `_load_pos_data_read`: `records.read(fields, ...)` with
        an empty list reads all fields). Turning that `[]` into an explicit
        whitelist — even one padded with our own required fields — silently
        breaks every OTHER module's pos.payment field (e.g. an analytic
        account added by a subsidiary/cost-center module): anything not in
        this hardcoded list stops reaching the frontend, and the client's
        `related_models` engine rejects it with "field does not exist" the
        moment something tries to set it. Only build the whitelist if some
        ancestor already narrowed it; otherwise, keep passing "all fields"
        through untouched.
        """
        res = super()._load_pos_data_fields(config)
        if not res:
            return res
        required = list(self._POS_PAYMENT_CORE_FIELDS) + [
            "foreign_rate",
            "foreign_amount",
            "foreign_currency_id",
        ]
        for name in required:
            if name not in res:
                res.append(name)
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
