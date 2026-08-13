from odoo import models


class PosOrder(models.Model):
    _inherit = "pos.order"

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
