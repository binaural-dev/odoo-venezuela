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

    def get_payments_order_refund(self):
        return self.payment_ids.read()

    def _prepare_refund_values(self, current_session):
        return super()._prepare_refund_values(current_session)

    def _get_invoice_lines_values(self, line_values, pos_order_line, move_type):
        # Odoo 19 added the ``move_type`` argument
        # (`point_of_sale/models/pos_order.py:220`). Forward it verbatim
        # and only inject the Venezuelan ``foreign_price``.
        res = super()._get_invoice_lines_values(line_values, pos_order_line, move_type)
        res["foreign_price"] = pos_order_line.foreign_price
        return res
