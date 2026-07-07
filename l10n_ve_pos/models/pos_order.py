from odoo import api, fields, models


class PosOrder(models.Model):
    _inherit = "pos.order"

    # ------------------------------------------------------------------
    # Odoo 19 load contract — contract-driven, no heuristics.
    #
    # The Odoo 19 base ``pos.order._load_pos_data_fields`` returns ``[]``
    # (see ``point_of_sale/models/pos_load_mixin.py`` and
    # ``point_of_sale/models/pos_order.py::read_pos_data``). That means
    # every real deployment MUST declare here the fields it wants the
    # frontend to receive, otherwise ``pos.order`` payloads reach the UI
    # empty and the sync layer breaks (e.g. ``constructOrdersDomain``
    # in ``devices_synchronisation.js`` calls
    # ``record.write_date.plus(...)`` and needs ``write_date`` to exist).
    #
    # We split the contract in three named lists so each entry is
    # explicit and traceable to the Odoo 19 source that requires it:
    #
    # * ``_ODOO19_ORDER_HEADER_FIELDS`` — fields the Odoo 19 UI reads to
    #   rehydrate a ``pos.order`` (uuid, session, state, currency, lines
    #   and payment relations, amounts).
    # * ``_ODOO19_ORDER_SYNC_FIELDS`` — fields Odoo 19 device
    #   synchronisation needs (``write_date`` is the critical one; used
    #   by ``constructOrdersDomain`` and by ``pos.order.line`` in core).
    # * ``_L10N_VE_ORDER_FIELDS`` — Venezuelan foreign-currency
    #   extension exposed by this module.
    #
    # A fail-fast guard at the end asserts none of the truly critical
    # keys is lost by a future ``super()`` change.
    # ------------------------------------------------------------------

    _ODOO19_ORDER_HEADER_FIELDS = (
        "id",
        "name",
        "uuid",
        # ``access_token`` is set by the frontend at order creation
        # (``pos_store.js::createNewOrder`` -> ``access_token: uuidv4()``)
        # and unconditionally popped by ``pos.order._process_order``
        # (``point_of_sale/models/pos_order.py:131`` -> ``del order['access_token']``).
        # If it's not part of the load contract, ``serializeForORM`` cannot
        # round-trip it back on the second sync (e.g. adding a payment to an
        # already synced draft order) and the backend crashes with
        # ``KeyError: 'access_token'`` on validation.
        "access_token",
        "pos_reference",
        "date_order",
        "state",
        "amount_total",
        "amount_tax",
        "amount_paid",
        "amount_return",
        "company_id",
        "session_id",
        "config_id",
        "currency_id",
        "pricelist_id",
        "partner_id",
        "lines",
        "payment_ids",
    )

    # ``write_date`` is required by Odoo 19 POS device sync.
    # Reference:
    #   /home/binaural19/odoo/addons/point_of_sale/static/src/app/utils/
    #     devices_synchronisation.js -> constructOrdersDomain()
    #     -> record.write_date.plus({ seconds: 1 })
    # Odoo 19 also lists ``write_date`` in ``pos.order.line._load_pos_data_fields``
    # (``pos_order.py:1608``); the same signal must exist on the header.
    _ODOO19_ORDER_SYNC_FIELDS = ("write_date",)

    _L10N_VE_ORDER_FIELDS = (
        "foreign_amount_total",
        "foreign_currency_rate",
    )

    _CRITICAL_LOAD_FIELDS = (
        "id",
        "uuid",
        "write_date",
        "session_id",
        "currency_id",
        "lines",
        "payment_ids",
        "amount_total",
    )

    foreign_currency_id = fields.Many2one(
        "res.currency", related="company_id.foreign_currency_id"
    )
    foreign_amount_total = fields.Float(
        string="Foreign Total", readonly=True, required=True
    )
    foreign_currency_rate = fields.Float(readonly=True, required=False)

    @api.model
    def _load_pos_data_fields(self, config):
        """Odoo 19 replacement for the removed Odoo 17 hooks
        (``_order_fields`` / ``_export_for_ui`` — dropped in
        ``2a5f1abf2e98``).

        Extends ``super()`` with the Odoo 19 header contract, the sync
        contract (``write_date``) and the Venezuelan foreign-currency
        extension. Every entry is justified in class-level constants,
        no dynamic ``self._fields`` heuristics — those hide contract
        drift and produce surprises across module upgrades.
        """
        res = super()._load_pos_data_fields(config) or []
        for name in (
            self._ODOO19_ORDER_HEADER_FIELDS
            + self._ODOO19_ORDER_SYNC_FIELDS
            + self._L10N_VE_ORDER_FIELDS
        ):
            if name not in res:
                res.append(name)

        missing = [name for name in self._CRITICAL_LOAD_FIELDS if name not in res]
        if missing:
            raise ValueError(
                f"l10n_ve_pos: missing critical pos.order load fields: {missing}"
            )
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
