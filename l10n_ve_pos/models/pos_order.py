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

    @api.model
    def get_refund_foreign_rate(self, order_ids):
        """Effective local-per-foreign rate the customer actually got on the
        original order's foreign tender.

        Returns ``sum(|amount|) / sum(|foreign_amount|)`` across the original
        order(s) payments made with a foreign-currency method. A refund uses
        this to value a foreign payment line at the EXACT rate the original
        payment was recorded with (mirror the customer's tender), instead of
        re-deriving a rate from the order's rounded aggregate totals — which
        drifts by a few cents. Returns ``0`` when there is no foreign tender
        to mirror (caller falls back to its normal conversion).
        """
        if not order_ids:
            return 0.0
        if isinstance(order_ids, int):
            order_ids = [order_ids]
        orders = self.browse(order_ids).exists()
        if not orders:
            return 0.0
        payments = orders.mapped("payment_ids").filtered(
            lambda p: p.payment_method_id.is_foreign_currency and p.foreign_amount
        )
        total_local = sum(abs(p.amount) for p in payments)
        total_foreign = sum(abs(p.foreign_amount) for p in payments)
        return total_local / total_foreign if total_foreign else 0.0

    def _prepare_refund_values(self, current_session):
        return super()._prepare_refund_values(current_session)

    def _get_invoice_lines_values(self, line_values, pos_order_line, move_type):
        # Odoo 19 added the ``move_type`` argument
        # (`point_of_sale/models/pos_order.py:220`). Forward it verbatim
        # and only inject the Venezuelan ``foreign_price``.
        res = super()._get_invoice_lines_values(line_values, pos_order_line, move_type)
        res["foreign_price"] = pos_order_line.foreign_price
        return res
