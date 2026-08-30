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
    def _complete_values_from_session(self, session, values):
        """Guarantee ``foreign_amount_total`` (required=True) is never NULL
        at INSERT time, regardless of which channel creates the order.

        Normally the POS frontend computes it client-side
        (``static/src/overrides/models/pos_order.js::serializeForORM``), but
        that patch only loads in the cashier app's asset bundle
        (``point_of_sale._assets_pos``). Any other channel that builds a
        ``pos.order`` without going through that bundle — e.g. the native
        Kiosk/Self-Order app, which ships its own separate bundle — never
        sends the field and the NOT NULL constraint used to raise a raw SQL
        error. ``setdefault`` makes this a no-op for the normal cashier flow
        (the value is already present), so it only fills the gap for
        channels that don't have it.
        """
        values = super()._complete_values_from_session(session, values)
        config = session.config_id
        values.setdefault(
            "foreign_amount_total",
            config._convert(values.get("amount_total") or 0.0, config.currency_id, config.foreign_currency_id),
        )
        values.setdefault(
            "foreign_currency_rate",
            config._get_pos_conversion_rate(config.currency_id, config.foreign_currency_id),
        )
        return values

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

    def _prepare_refund_values(self, current_session):
        return super()._prepare_refund_values(current_session)

    def _get_invoice_lines_values(self, line_values, pos_order_line, move_type):
        # Odoo 19 added the ``move_type`` argument
        # (`point_of_sale/models/pos_order.py:220`). Forward it verbatim
        # and only inject the Venezuelan ``foreign_price``.
        res = super()._get_invoice_lines_values(line_values, pos_order_line, move_type)
        res["foreign_price"] = pos_order_line.foreign_price
        return res
