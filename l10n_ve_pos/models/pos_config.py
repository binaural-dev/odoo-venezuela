from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

# Integra 16 tiene varios campos con readonly=True, revisar para migrar


class PosConfig(models.Model):
    _inherit = "pos.config"

    foreign_currency_id = fields.Many2one(
        "res.currency", related="company_id.foreign_currency_id"
    )

    foreign_inverse_rate = fields.Float(
        help="Rate that will be used as factor to multiply of the foreign currency for moves.",
        compute="_compute_rate",
        digits=(16, 15),
        default=0.0,
        readonly=False,
    )
    foreign_rate = fields.Float(
        compute="_compute_rate",
        digits="Tasa",
        default=0.0,
        readonly=False,
    )
    pos_show_free_qty = fields.Boolean(related="company_id.pos_show_free_qty")
    sell_kit_from_another_store = fields.Boolean(default=False)
    pos_show_just_products_with_available_qty = fields.Boolean(
        related="company_id.pos_show_just_products_with_available_qty"
    )
    pos_search_cne = fields.Boolean(related="company_id.pos_search_cne")
    amount_to_zero = fields.Boolean("Amount to zero")
    activate_barcode_strict_mode = fields.Boolean(
        help="Activate product entry with barcode in strict mode"
    )
    validate_phone_in_pos = fields.Boolean(default=False)

    @api.depends("foreign_currency_id", "foreign_inverse_rate", "foreign_rate")
    def _compute_rate(self):
        """
        Compute the rate of the pos using the compute_rate method of the res.currency.rate model.
        """
        rate = self.env["res.currency.rate"]
        for config in self:
            rate_values = rate.compute_rate(
                config.foreign_currency_id.id, fields.Date.today()
            )
            config.update(rate_values)

    # ---------------------------------------------------------------
    # POS-scoped currency conversion
    # ---------------------------------------------------------------
    #
    # MIRROR CONTRACT:
    #   This method mirrors res.currency._convert (odoo/addons/base/models/
    #   res_currency.py) in shape and precision semantics: multiply
    #   `from_amount` by the raw rate (all digits, no early rounding) and
    #   round only the final result with `to_currency.round(...)`.
    #
    # WHY WE DON'T CALL res.currency._convert DIRECTLY:
    #   res.currency._convert reads `res.currency.rate` by date. In Venezuela
    #   the operative rate lives on `pos.config.foreign_rate` /
    #   `foreign_inverse_rate`, which is *computed once* from `res.currency.rate`
    #   when the config is loaded and effectively frozen for the session.
    #   Using the historical rate mid-session would desync tickets vs. invoices.
    #
    # PRECISION RULE (business, stated by user):
    #   BS * TASA_INVERSA_CON_TODOS_LOS_DIGITOS → USD
    #   USD * TASA_DIRECTA → BS
    #   Round only the result, never the rate.
    #
    # KEEP IN SYNC WITH:
    #   static/src/overrides/models/pos_order.js :: PosOrder._convert
    #
    def _get_pos_conversion_rate(self, from_currency, to_currency):
        """Return the raw rate to convert 1 unit of ``from_currency`` to
        ``to_currency`` using this POS config's operative rates.

        Semantics (see l10n_ve_rate.res_currency_rate.compute_rate):

            pos.config exposes two rates whose meaning depends on which
            currency is foreign:
              * main=VEF, foreign=USD (classic VE):
                  foreign_rate         = inverse_company_rate (~0.00148)
                  foreign_inverse_rate = company_rate         (~675)
              * main=USD, foreign=VEF:
                  foreign_rate         = company_rate         (~675)
                  foreign_inverse_rate = company_rate         (~675)

            The invariant enforced by compute_rate is:
              ``foreign_rate`` is ALWAYS the multiplier to go
              main → foreign (i.e. local_amount * foreign_rate = foreign_amount).
              It is also the "user-facing" rate shown in the UI.

            Therefore:
              main → foreign  ==>  return foreign_rate
              foreign → main  ==>  return 1 / foreign_rate

            We do NOT use ``foreign_inverse_rate`` directly for arithmetic:
            its meaning is context-dependent and only stable as "the value
            stored on account.move.line for reporting", not as a conversion
            factor.

        PRECISION: ``foreign_rate`` is stored with digits="Tasa" (custom
        high precision). Read the raw value; never round the rate itself.
        Rounding is done by ``_convert`` at the final result via
        ``to_currency.round()``.

        Returns 0.0 when neither side is the foreign currency; callers must
        treat 0.0 as "no conversion possible" and NOT silently proceed.
        """
        self.ensure_one()
        if from_currency == to_currency:
            return 1.0
        foreign = self.foreign_currency_id
        rate = self.foreign_rate
        if not rate:
            return 0.0
        # main → foreign
        if foreign and to_currency == foreign and from_currency != foreign:
            return rate
        # foreign → main
        if foreign and from_currency == foreign and to_currency != foreign:
            return 1.0 / rate
        return 0.0

    def _convert(self, from_amount, from_currency, to_currency, round=True):  # noqa: A002
        """POS-scoped currency conversion. See MIRROR CONTRACT above.

        :param from_amount: amount in ``from_currency`` units
        :param from_currency: source ``res.currency``
        :param to_currency: target ``res.currency``
        :param round: whether to round the result to ``to_currency`` precision
        :return: converted amount (0.0 when no rate is available)
        """
        self.ensure_one()
        if not from_amount:
            return 0.0
        if from_currency == to_currency:
            return to_currency.round(from_amount) if round else from_amount
        rate = self._get_pos_conversion_rate(from_currency, to_currency)
        if not rate:
            return 0.0
        result = from_amount * rate
        return to_currency.round(result) if round else result

    def _action_to_open_ui(self):
        res = super()._action_to_open_ui()
        if (
            not self.current_session_id.foreign_currency_id
            or not self.current_session_id.foreign_currency_id.active
        ):
            raise ValidationError(
                _("The session must have a foreign currency or active")
            )
        return res
