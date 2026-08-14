from odoo import api, models


class PosOrder(models.Model):
    _inherit = "pos.order"

    @api.model
    def _check_pos_order(self, pos_config, order, device_type, table=None):
        """Force ``to_invoice=True`` on every Kiosk order.

        ``l10n_ve_pos`` requires every POS sale to emit a fiscal invoice
        (SENIAT), and enforces it on the cashier by patching the JS
        ``PosOrder`` in the ``point_of_sale._assets_pos`` bundle
        (``static/src/overrides/models/pos_order.js`` — ``setup``/
        ``serializeForORM``). The Kiosk/Self-Order app ships a *different*
        asset bundle (``pos_self_order.assets``) that never loads that patch,
        so the client sends no ``to_invoice`` and the core ``_check_pos_order``
        copies that missing value straight through — the Kiosk order ends up
        NOT invoiced.

        Force it server-side here, the one method that builds the Kiosk order
        vals. Gated to ``self_ordering_mode == 'kiosk'`` (same scope as the
        cédula identification flow, which is what guarantees the order carries
        a real ``partner_id`` to invoice): the ``mobile``/QR flow has no such
        guarantee and must not be forced to invoice against the generic
        consumer.
        """
        vals = super()._check_pos_order(pos_config, order, device_type, table)
        if pos_config.self_ordering_mode == "kiosk":
            vals["to_invoice"] = True
        return vals

    def recompute_prices(self):
        """``recompute_prices`` (pos_self_order) recalculates ``amount_total``
        authoritatively from the real catalog after the Kiosk/Self-Order
        controller creates an order, to defend against a tampered client
        payload. It never touches the Venezuelan foreign-currency fields,
        so ``l10n_ve_pos``'s provisional value (from
        ``_complete_values_from_session``, based on the client-submitted
        total) goes stale the moment this recompute corrects the total.

        Mirror the same ``pos.config._convert``/``_get_pos_conversion_rate``
        contract used everywhere else in ``l10n_ve_pos`` to keep the foreign
        total in sync with the now-authoritative local total.
        """
        super().recompute_prices()
        config = self.config_id
        self.foreign_amount_total = config._convert(
            self.amount_total, self.currency_id, config.foreign_currency_id
        )
        self.foreign_currency_rate = config._get_pos_conversion_rate(
            self.currency_id, config.foreign_currency_id
        )
