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

        SEMÁNTICA REAL (verificada en DB pos + core Odoo 19 res_currency.py):

            pos.config._compute_rate delega a l10n_ve_rate.compute_rate,
            que para foreign=USD, main=VEF devuelve:
              foreign_rate         = rate.inverse_company_rate  (~675, GRANDE)
              foreign_inverse_rate = rate.company_rate          (~0.001481, CHICO)

            Del core Odoo:
              company_rate         = rate / company_currency_rate
              inverse_company_rate = 1 / company_rate

            Para USD el 2026-07-07 con res.currency.rate.rate = 0.0014816340...:
              company_rate         = 0.001481 / 1 (VEF=base) = 0.001481 (CHICO)
              inverse_company_rate = 1 / 0.001481           = 674.93   (GRANDE)

            Entonces l10n_ve_rate expone:
              pos_config.foreign_rate         = 674.93   ("USD per VEF" — lo que el usuario VE en la UI si compra en dólares)
              pos_config.foreign_inverse_rate = 0.001481 ("VEF per USD" — el multiplicador REAL para pasar de VEF a USD)

        CONVERSIÓN CORRECTA (regla del usuario):
            main (VEF) → foreign (USD): usar foreign_inverse_rate (0.001481)
              VEF * 0.001481 = USD ✓
            foreign (USD) → main (VEF): usar foreign_rate (674.93)
              USD * 674.93 = VEF ✓

        En el caso foreign=VEF, main=USD:
            compute_rate devuelve foreign_rate = foreign_inverse_rate = company_rate.
            Ambos coinciden, cualquiera funciona.

        PRECISION: ``foreign_inverse_rate`` está definido con digits=(16,15)
        para preservar los 15 dígitos de precisión de la tasa BCV.
        Nunca redondear la tasa; redondear solo el resultado con
        ``to_currency.round()``.

        Returns 0.0 when neither side is the foreign currency; callers must
        treat 0.0 as "no conversion possible" and NOT silently proceed.

        KEEP IN SYNC WITH:
          static/src/overrides/models/pos_order.js :: _getPosConversionRate
        """
        self.ensure_one()
        if from_currency == to_currency:
            return 1.0
        foreign = self.foreign_currency_id
        if not foreign:
            return 0.0
        # main → foreign: multiplicar por foreign_inverse_rate (CHICO)
        if to_currency == foreign and from_currency != foreign:
            rate = self.foreign_inverse_rate
            return rate if rate else 0.0
        # foreign → main: multiplicar por foreign_rate (GRANDE)
        if from_currency == foreign and to_currency != foreign:
            rate = self.foreign_rate
            return rate if rate else 0.0
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
