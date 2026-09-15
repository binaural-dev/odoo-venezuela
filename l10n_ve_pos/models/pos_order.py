from odoo import api, fields, models


class PosOrder(models.Model):
    _inherit = "pos.order"

    foreign_currency_id = fields.Many2one(
        "res.currency", related="company_id.foreign_currency_id"
    )
    foreign_amount_total = fields.Float(
        string="Foreign Total", readonly=True, required=True
    )
    foreign_currency_rate = fields.Float(readonly=True, required=False)

    @api.model
    def _load_pos_data_read(self, records, config):
        """Inject only the Venezuelan foreign-currency values on top of
        whatever core Odoo 19 already returned. We do NOT touch the
        field contract (``_load_pos_data_fields``) — core owns that.
        """
        read_records = super()._load_pos_data_read(records, config)
        if not read_records:
            return read_records
        records_by_id = {r.id: r for r in records}
        for record in read_records:
            source = records_by_id.get(record["id"])
            if not source:
                continue
            record["foreign_amount_total"] = source.foreign_amount_total
            record["foreign_currency_rate"] = source.foreign_currency_rate
        return read_records

    def _prepare_invoice_vals(self):
        self.ensure_one()
        res = super()._prepare_invoice_vals()
        res.update(
            {
                "foreign_rate": self.foreign_currency_rate,
                "foreign_inverse_rate": self.foreign_currency_rate,
                "manually_set_rate": True,
            }
        )
        return res

    def _amount_to_foreign(self, amount):
        """Convert a POS main-currency amount (Bs.) into the company's foreign
        currency (USD) using this order's rate, rounded to the foreign
        currency precision.

        Mirrors the frontend ``pos.order.localToForeign`` used to fill
        ``foreign_amount`` on every regular payment line, so any line created
        server-side (e.g. the change/vuelto line) gets the same value.
        """
        self.ensure_one()
        rate = self.foreign_currency_rate
        if not rate:
            return 0.0
        foreign_amount = amount * rate
        foreign_currency = self.foreign_currency_id
        if foreign_currency:
            foreign_amount = foreign_currency.round(foreign_amount)
        return foreign_amount

    def _process_payment_lines(self, pos_order, order, pos_session, draft):
        """Backfill the foreign-currency amount on the change (vuelto) line.

        Odoo core creates the change payment server-side here (``is_change``)
        without a ``foreign_amount``/``foreign_rate``. Both the invoice payment
        moves (``pos.payment._create_payment_moves``) and the session-close
        cross moves (``pos.session``) build the alternate-currency columns
        (``foreign_debit``/``foreign_credit``) from ``payment.foreign_amount``,
        so a missing value left the change move with USD 0,00 and the alternate
        currency unbalanced against the invoice (ticket #15126). Populate it at
        the source so every downstream consumer reads a correct value.
        """
        res = super()._process_payment_lines(pos_order, order, pos_session, draft)
        change_payments = order.payment_ids.filtered(
            lambda payment: payment.is_change
            and payment.amount
            and not payment.foreign_amount
        )
        for payment in change_payments:
            payment.write(
                {
                    "foreign_amount": order._amount_to_foreign(payment.amount),
                    "foreign_rate": order.foreign_currency_rate,
                }
            )
        return res

    @api.model
    def get_payments_order_refund(self, order_ids):
        if not order_ids:
            return []
        if isinstance(order_ids, int):
            order_ids = [order_ids]
        orders = self.browse(order_ids).exists()
        if not orders:
            return []
        return orders.mapped("payment_ids").read()

    def _prepare_refund_values(self, current_session):
        return super()._prepare_refund_values(current_session)

    def _get_invoice_lines_values(self, line_values, pos_order_line, move_type):
        # Odoo 19 added the ``move_type`` argument
        # (`point_of_sale/models/pos_order.py:220`). Forward it verbatim
        # and only inject the Venezuelan ``foreign_price``.
        res = super()._get_invoice_lines_values(line_values, pos_order_line, move_type)
        res["foreign_price"] = pos_order_line.foreign_price
        return res
