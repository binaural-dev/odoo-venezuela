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
    tender_currency_rates = fields.Json(
        compute="_compute_tender_currency_rates",
        help="Operative rates of the tender currencies of the payment methods of the PoS, by "
        "currency id: foreign_rate (tender currency → PoS currency) and foreign_inverse_rate "
        "(PoS currency → tender currency), same pair as foreign_rate / foreign_inverse_rate.",
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
    allow_product_creation_in_pos = fields.Boolean(
        "Allow product creation",
        default=False,
        help="Allow creating products from the PoS screen",
    )

    @api.depends("foreign_currency_id", "foreign_inverse_rate", "foreign_rate")
    def _compute_rate(self):
        """
        Compute the rate of the pos using the compute_rate method of the res.currency.rate model.
        """
        rate = self.env["res.currency.rate"]
        for config in self:
            # La caja puede abrirse sin tasa del día (la conversión devuelve 0.0):
            # este compute no debe bloquear la vista de la configuración.
            rate_values = rate.compute_rate(
                config.foreign_currency_id.id,
                fields.Date.context_today(config),
                raise_if_not_found=False,
            )
            config.update(rate_values)

    @api.depends("payment_method_ids.tender_currency_id")
    def _compute_tender_currency_rates(self):
        """Tasas de las monedas de cobro (``pos.payment.method.tender_currency_id``)
        con la misma fuente y la misma orientación que ``_compute_rate``:
        ``compute_rate`` a la fecha del usuario, ``foreign_rate`` = moneda de
        cobro → caja (la GRANDE, Bs por €) y ``foreign_inverse_rate`` = caja →
        moneda de cobro (la CHICA). Viven en la caja porque ``pos.config`` se
        carga entero en cada apertura (``pos.load.mixin._last_server_date_to_load``
        no lo filtra por ``write_date``): el PdV recibe siempre la tasa del día.
        Sin tasa del día, ambas valen 0 y la conversión no es posible.
        """
        rate = self.env["res.currency.rate"]
        for config in self:
            rates = {}
            for currency in config.payment_method_ids.tender_currency_id:
                values = rate.compute_rate(
                    currency.id,
                    fields.Date.context_today(config),
                    raise_if_not_found=False,
                )
                rates[str(currency.id)] = {
                    "foreign_rate": values.get("foreign_rate") or 0.0,
                    "foreign_inverse_rate": values.get("foreign_inverse_rate") or 0.0,
                }
            config.tender_currency_rates = rates

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

        En el caso foreign=VEF, main=USD la regla es la misma; solo cambian
        las magnitudes. compute_rate devuelve:
              pos_config.foreign_rate         = 0.001244 (inverse_company_rate)
              pos_config.foreign_inverse_rate = 803.34   (company_rate)
            USD * 803.34 = VEF ✓   VEF * 0.001244 = USD ✓
        (compute_rate solo devuelve las dos tasas iguales cuando la moneda
        foránea es la misma de la compañía.)

        PRECISION: ``foreign_inverse_rate`` está definido con digits=(16,15)
        para preservar los 15 dígitos de precisión de la tasa BCV.
        Nunca redondear la tasa; redondear solo el resultado con
        ``to_currency.round()``.

        TERCERA MONEDA (moneda de cobro de un método, p. ej. EUR): sus tasas
        viven en ``tender_currency_rates`` con la misma orientación, así que
        EUR → Bs multiplica por su ``foreign_rate`` (GRANDE) y Bs → EUR por su
        ``foreign_inverse_rate`` (CHICO). Entre la moneda de cobro y la alterna
        (EUR → USD) se pasa por la caja multiplicando las dos tasas, sin
        redondear ninguna: EUR → Bs × Bs → USD. Ver ``_get_tender_conversion_rate``.
        Los pares sin moneda de cobro siguen la regla de siempre (el lado que
        no es la alterna es la caja).

        Returns 0.0 when neither side is the foreign currency nor a tender
        currency, or the rate of the day is missing; callers must treat 0.0 as
        "no conversion possible" and NOT silently proceed.

        KEEP IN SYNC WITH:
          static/src/overrides/models/pos_order.js :: _getPosConversionRate
        """
        self.ensure_one()
        if from_currency == to_currency:
            return 1.0
        tender_currencies = self._get_tender_currencies()
        if from_currency in tender_currencies or to_currency in tender_currencies:
            return self._get_tender_conversion_rate(from_currency, to_currency)
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

    def _get_tender_currencies(self):
        """Monedas de cobro con tasa en esta caja (``tender_currency_rates``)."""
        self.ensure_one()
        return self.env["res.currency"].browse(
            [int(currency_id) for currency_id in (self.tender_currency_rates or {})]
        )

    def _get_tender_conversion_rate(self, from_currency, to_currency):
        """Tasa entre una moneda de cobro y la caja, la alterna u otra moneda
        de cobro: cada lado aporta su par ``(moneda → caja, caja → moneda)``
        (``_get_pos_currency_rate_pair``) y la tasa es
        ``(from → caja) × (caja → to)``, sin redondear. 0.0 si algún lado no
        tiene tasa.

        KEEP IN SYNC WITH:
          static/src/overrides/models/pos_order.js :: _getTenderConversionRate
        """
        self.ensure_one()
        from_rates = self._get_pos_currency_rate_pair(from_currency)
        to_rates = self._get_pos_currency_rate_pair(to_currency)
        if not from_rates or not to_rates:
            return 0.0
        return (from_rates[0] * to_rates[1]) or 0.0

    def _get_pos_currency_rate_pair(self, currency):
        """``(currency → caja, caja → currency)`` con las tasas operativas de
        esta caja para la caja (1, 1), la alterna y las monedas de cobro, o
        ``None`` para otra moneda.

        KEEP IN SYNC WITH:
          static/src/overrides/models/pos_order.js :: _getPosCurrencyRatePair
        """
        self.ensure_one()
        if not currency:
            return None
        if currency == self.currency_id:
            return 1.0, 1.0
        if currency == self.foreign_currency_id:
            return self.foreign_rate or 0.0, self.foreign_inverse_rate or 0.0
        rates = (self.tender_currency_rates or {}).get(str(currency.id))
        if rates:
            return rates.get("foreign_rate") or 0.0, rates.get("foreign_inverse_rate") or 0.0
        return None

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

    def _get_move_foreign_rate_vals(self, main_to_foreign_rate):
        """Rates stamped on a POS move (invoice, payment move) valued at the
        ``main_to_foreign_rate`` multiplier (company currency → foreign, the
        same orientation as ``foreign_inverse_rate`` in
        ``_get_pos_conversion_rate``).

        Same pair ``l10n_ve_rate`` (``res.currency.rate.compute_rate``) gives
        every other move and this config: ``foreign_inverse_rate`` is the
        multiplier ``l10n_ve_accountant`` computes the lines' foreign amounts
        with, and ``foreign_rate`` its inverse, the rate shown on the move and
        read by the digital invoice and the withholdings. Holds for both
        company currencies: 803.34 / 0.001244… with the company in Bs,
        0.001244… / 803.34 with the company in USD. The multiplier is the
        order's frozen one, not today's rate of this config, which is why the
        inverse is built here instead of reading ``self.foreign_rate``.

        :param main_to_foreign_rate: company currency → foreign multiplier
        :return: ``account.move`` values; empty without a rate, so the move
            takes the rate of its date instead of a fixed 0
        """
        if not main_to_foreign_rate:
            return {}
        return {
            "foreign_inverse_rate": main_to_foreign_rate,
            "foreign_rate": 1 / main_to_foreign_rate,
            "manually_set_rate": True,
        }

    def _check_before_creating_new_session(self):
        res = super()._check_before_creating_new_session()
        self._check_cross_move_accounts()
        self._check_tender_cash_methods_order()
        return res

    def _check_tender_cash_methods_order(self):
        """El core toma como efectivo de la caja el primer método de efectivo:
        en él registra el vuelto (``pos.order._process_payment_lines``) y su
        diario es el del arqueo (``pos.session.cash_journal_id``). Un método en
        una tercera moneda no puede ser ese: el vuelto se entrega en la moneda
        de la caja.
        """
        self.ensure_one()
        first_cash_method = self.payment_method_ids.filtered("is_cash_count")[:1]
        if first_cash_method.tender_currency_id:
            raise ValidationError(
                _(
                    "The first cash payment method of the Point of Sale %(pos)s must be the one in "
                    "%(currency)s: the change is given with it. %(method)s is collected in "
                    "%(tender)s, move it after that one in the payment methods list.",
                    pos=self.name,
                    currency=self.currency_id.name,
                    method=first_cash_method.name,
                    tender=first_cash_method.tender_currency_id.name,
                )
            )

    def _check_cross_move_accounts(self):
        """Refuse to open a session whose cross moves would miss an account.

        Same idea as the native ``_check_profit_loss_cash_journal``: a
        foreign-currency method with both cross journals set will need the
        accounts listed by ``pos.session._get_cross_move_missing_accounts``
        (on opening, with the foreign cash drawer's opening difference, and on
        closing). Without them the cross move used to be built with a NULL
        ``account_id`` and the opening crashed on
        ``account_move_line_check_accountable_required_fields``.
        """
        self.ensure_one()
        # A virtual session of this config: which methods cross depends on the
        # session (e.g. its currency), and other modules extend that per session.
        session = self.env["pos.session"].new({"config_id": self.id})
        missing = [
            f"- {method.name} → {account}"
            for method in self.payment_method_ids
            if session._is_cross_move_eligible(method)
            for account in session._get_cross_move_missing_accounts(method)
        ]
        if missing:
            raise ValidationError(
                _(
                    "The session cannot be opened: the cross move of these "
                    "payment methods needs accounts that are not set:\n%(accounts)s\n"
                    "Set them in Accounting > Configuration > Journals.",
                    accounts="\n".join(missing),
                )
            )

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

    def check_stock_availability(self, qty_by_product):
        """Storable products whose quantity in the order exceeds the stock on
        hand of the PoS source location (``amount_to_zero``).

        Called by the PoS before the payment screen, so the order is blocked
        before anything is printed on the fiscal machine. On hand, not free
        quantity: what other confirmed orders reserved does not block, the
        order being sold has priority.

        :param dict qty_by_product: ``{product_id: quantity}`` of the order.
        :return: list of ``{"name", "requested", "available"}``.
        """
        self.ensure_one()
        if not self.amount_to_zero or not qty_by_product:
            return []
        qty_by_product = {int(product_id): qty for product_id, qty in qty_by_product.items()}
        location = self.picking_type_id.default_location_src_id
        if not location:
            # Without a source location the quantity would be computed over
            # every internal location of the company: do not validate.
            return []
        # exists(): a product deleted after the PoS loaded it is skipped
        # instead of raising MissingError.
        products = (
            self.env["product.product"]
            .browse(list(qty_by_product))
            .exists()
            .with_context(location=location.id)
            .filtered("is_storable")
        )
        return [
            {
                "name": product.display_name,
                "requested": qty_by_product[product.id],
                "available": product.qty_available,
            }
            for product in products
            if product.uom_id.compare(qty_by_product[product.id], product.qty_available) > 0
        ]
