from odoo import api, fields, models


class PosOrder(models.Model):
    _inherit = "pos.order"

    # ----- Odoo 19 serialization contract -----
    # The Odoo 19 base ``pos.order._load_pos_data_fields`` returns ``[]``;
    # ``read_pos_data`` (``pos_order.py:1297``) and ``action_pos_order_cancel``
    # (``:1219``) rely on this hook to know which fields to expose back to
    # the POS UI. Without these fields, the read-back payload would be
    # empty and the frontend would lose every Venezuelan foreign-currency
    # value when the order is reloaded.
    foreign_currency_id = fields.Many2one(
        "res.currency", related="company_id.foreign_currency_id"
    )
    foreign_amount_total = fields.Float(
        string="Foreign Total", readonly=True, required=True
    )
    foreign_currency_rate = fields.Float(readonly=True, required=False)

    @api.model
    def _load_pos_data_fields(self, config):
        """Odoo 19 replacement for the Odoo 17 ``_order_fields`` /
        ``_export_for_ui`` hooks (both removed in commit
        ``2a5f1abf2e98 [IMP] pos_*: refactoring with related models
        part 2``).

        We MUST keep the Odoo 19 required stored fields + key relational
        dependencies (otherwise the frontend cannot render/reload the order)
        AND expose
        the Venezuelan ``foreign_amount_total`` / ``foreign_currency_rate``
        so the read-back payload survives the round trip.
        """
        res = super()._load_pos_data_fields(config) or []
        required_stored_fields = [
            name
            for name, field in self._fields.items()
            if field.store and field.required
        ]

        dependency_fields = [
            "id",
            "name",
            "uuid",
            "date_order",
            "state",
            "company_id",
            "session_id",
            "config_id",
            "currency_id",
            "partner_id",
            "lines",
            "payment_ids",
        ]

        for name in required_stored_fields + dependency_fields + [
            "foreign_amount_total",
            "foreign_currency_rate",
        ]:
            if name not in res:
                res.append(name)

        # Fail-fast guard: if upstream changes and we somehow lose any critical
        # key, raise immediately instead of silently degrading behavior.
        critical = (
            "id",
            "uuid",
            "session_id",
            "currency_id",
            "lines",
            "payment_ids",
            "amount_total",
        )
        missing = [name for name in critical if name not in res]
        if missing:
            raise ValueError(f"l10n_ve_pos: missing critical pos.order load fields: {missing}")
        return res

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

    def _get_invoice_lines_values(self, line_values, pos_order_line):
        # NOTE: Odoo 19 added a third ``move_type`` arg to this hook
        # (``addons/point_of_sale/models/pos_order.py:220``). The l10n_ve
        # override intentionally keeps the legacy 2-arg signature because
        # invoicing belongs to Slice E (see ``tasks.md``, E.2). Forcing
        # the 3-arg signature now would call ``super()`` with a missing
        # ``move_type`` and is out of scope for Slice B.
        res = super()._get_invoice_lines_values(line_values, pos_order_line)
        res["foreign_price"] = pos_order_line.foreign_price
        return res
