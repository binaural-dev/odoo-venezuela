import hmac
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

# BCV publishes each rate as "VEF units per 1 unit of the foreign currency"
# (e.g. 791.6667 VEF per 1 USD).
VEF_CURRENCY_CODE = "VEF"

# The currencies BCV Sync's scraper actually sends in every payload (see
# apps/worker/src/scrapers/bcv.scraper.ts's MAPEO_MONEDA in the BCV Sync
# repo). Kept here as a plain constant, not discovered dynamically, so it
# must be kept in sync by hand if that list ever changes.
BCV_PUBLISHED_CURRENCIES = {"USD", "EUR", "CNY", "TRY", "RUB"}


class ResCompany(models.Model):
    _inherit = "res.company"

    bcv_sync_api_key = fields.Char(
        string="BCV Sync API Key",
        copy=False,
        groups="base.group_system",
        help=(
            "Token compartido que BCV Sync envia en el header "
            "'Authorization: Bearer <token>' al llamar a POST /api/tasas-bcv. "
            "Se puede generar desde aqui (boton 'Generar Token' en Ajustes) o "
            "pegar uno ya generado en el panel de BCV Sync; en ambos casos, "
            "el valor final debe coincidir exactamente con el configurado "
            "alli para el cliente/URL de esta compania."
        ),
    )

    @api.model
    def _bcv_sync_get_company_by_token(self, token):
        """Finds the company whose ``bcv_sync_api_key`` matches ``token``.

        Compares against every company with a key configured using
        ``hmac.compare_digest`` (constant time) so timing doesn't leak
        whether the received token is correct or not.
        """
        if not token:
            return self.browse()

        companies = self.sudo().with_context(active_test=False).search(
            [("bcv_sync_api_key", "!=", False)]
        )
        match = self.browse()
        for company in companies:
            if hmac.compare_digest(token, company.bcv_sync_api_key or ""):
                match = company
        return match

    def _bcv_sync_process_tasas(self, tasas):
        """Idempotently applies the ``tasas`` entries received from BCV
        Sync for this company (always runs against the root company, see
        the controller).

        Each ``tasas`` entry is a dict with ``moneda``/``valor``/
        ``fecha_valor`` exactly as they arrive in the payload (see
        ``ODOO_INTEGRATION.md`` in the BCV Sync repo). This company's own
        accounting currency decides which res.currency.rate gets written
        (see ``_bcv_sync_resolve_target_currency_code``): when it's VEF,
        ``moneda`` itself is the target and the raw value applies as-is;
        when it's one of BCV's own published currencies (ex. USD), VEF
        becomes the target and only the entry whose ``moneda`` matches
        this company's currency carries a usable cross-rate (the raw
        value has to be inverted -- see below). Any other accounting
        currency skips the whole payload, there's nothing to convert
        against.

        An entry is skipped -without aborting the rest of the payload-
        when:

        - it doesn't resolve to a target currency for this company (see
          above);
        - the target currency isn't active/used in this Odoo (only
          currencies the company actually has enabled are considered);
        - the value can't be parsed as a positive number;
        - fecha_valor doesn't have a valid format;
        - ``_bcv_sync_is_valid_rate_date`` (this module's own date logic,
          see below) rejects fecha_valor for today;
        - fecha_valor is today and this company already has a stored rate
          for today -- once today's rate is set, later runs the same day
          never change it (accounting stability: a rate in effect during
          the day must not silently change under transactions already
          posted). This does not apply to advance (future) dates, which
          keep getting refreshed on every run until they become "today".

        Returns a summary ``{"applied": [...], "skipped": [...]}``
        (currency codes) only for the caller's logging/observability.
        """
        self.ensure_one()
        # Rates are always saved/queried against the root company (see
        # `res.currency.rate._bcv_sync_upsert`); make sure we also decide
        # against that same company, regardless of whether the token
        # matched a child company.
        self = self.root_id
        applied = []
        skipped = []

        company_currency = self.currency_id.name
        if company_currency != VEF_CURRENCY_CODE and (
            company_currency not in BCV_PUBLISHED_CURRENCIES
        ):
            _logger.warning(
                "BCV Sync: company '%s' has '%s' as its accounting "
                "currency, which is neither VEF nor a currency BCV Sync "
                "publishes a VEF cross-rate for; skipping the whole "
                "payload, there is nothing to convert against.",
                self.display_name,
                company_currency,
            )
            return {
                "applied": applied,
                "skipped": [entry.get("moneda") for entry in tasas],
            }

        today = fields.Date.context_today(self)
        # No `active_test=False` here on purpose: only currencies the
        # company actually has active/enabled are considered. A currency
        # BCV Sync sends that this Odoo never turned on is skipped, not
        # silently tracked.
        currency_model = self.env["res.currency"].sudo()
        rate_model = self.env["res.currency.rate"].sudo()

        for entry in tasas:
            moneda = (entry.get("moneda") or "").strip().upper()

            target_code = self._bcv_sync_resolve_target_currency_code(
                company_currency, moneda
            )
            if not target_code:
                skipped.append(moneda)
                continue

            currency = currency_model.search([("name", "=", target_code)], limit=1)
            if not currency:
                _logger.info(
                    "BCV Sync: target currency '%s' not recognized/active, "
                    "skipping that entry.",
                    target_code,
                )
                skipped.append(moneda)
                continue

            value = self._bcv_sync_parse_valor(entry.get("valor"))
            if value is None:
                _logger.warning(
                    "BCV Sync: invalid valor '%s' for %s, skipping that entry.",
                    entry.get("valor"),
                    moneda,
                )
                skipped.append(moneda)
                continue

            published_date = self._bcv_sync_parse_fecha_valor(
                entry.get("fecha_valor")
            )
            if not published_date:
                _logger.warning(
                    "BCV Sync: invalid fecha_valor '%s' for %s, skipping "
                    "that entry.",
                    entry.get("fecha_valor"),
                    moneda,
                )
                skipped.append(moneda)
                continue

            if not self._bcv_sync_is_valid_rate_date(today, published_date):
                _logger.info(
                    "BCV Sync: fecha_valor %s for %s does not apply today "
                    "(%s) per can_update_habil_days=%s, skipping.",
                    published_date,
                    moneda,
                    today,
                    self.can_update_habil_days,
                )
                skipped.append(moneda)
                continue

            if published_date == today and rate_model.search_count(
                [
                    ("currency_id", "=", currency.id),
                    ("company_id", "=", self.id),
                    ("name", "=", today),
                ]
            ):
                _logger.info(
                    "BCV Sync: %s already has a stored rate for today "
                    "(%s), keeping the existing value.",
                    moneda,
                    today,
                )
                skipped.append(moneda)
                continue

            # BCV always publishes "VEF units per 1 unit of moneda". When
            # this company's own currency is VEF, that's exactly the
            # res.currency.rate value we want for the `moneda` currency.
            # When this company's own currency is `moneda` itself (the
            # other supported case, see _bcv_sync_resolve_target_currency_code),
            # the rate is now being stored against VEF instead, from
            # `moneda`'s point of view -- which requires the reciprocal.
            # Verified against Odoo's own res.currency._convert (not just
            # the raw field): with company currency VEF, `value` stored
            # directly on the foreign currency's row makes
            # currency._convert(100, target=VEF, company=self) return
            # 100*value, correct. With company currency `moneda`,
            # 1/value stored on the VEF row makes
            # currency._convert(100, target=VEF, company=self) return
            # the same 100*value -- also correct, and the reverse
            # direction (VEF -> moneda) checks out too.
            rate_to_store = (
                value if company_currency == VEF_CURRENCY_CODE else 1.0 / value
            )
            rate_model._bcv_sync_upsert(currency, self, published_date, rate_to_store)
            applied.append(moneda)

        return {"applied": applied, "skipped": skipped}

    @api.model
    def _bcv_sync_resolve_target_currency_code(self, company_currency, moneda):
        """Given this company's own accounting currency and the
        ``moneda`` code of one ``tasas`` entry, returns the
        ``res.currency`` code we should write a rate against for this
        company, or ``None`` if this entry doesn't apply to it.

        - Company currency is VEF: ``moneda`` itself is the target (BCV's
          own currency codes, e.g. USD, are the "foreign" ones from a VEF
          company's point of view).
        - Company currency is one of BCV's published currencies (see
          ``BCV_PUBLISHED_CURRENCIES``) and matches ``moneda``: VEF
          becomes the target instead -- from this company's point of
          view, VEF is now the "foreign" currency, and this is the only
          entry in the payload that carries a usable cross-rate for it
          (BCV Sync never publishes one currency directly against
          another, only against VEF, so nothing else in the same payload
          can be placed for this company).
        - Anything else (a currency BCV Sync doesn't publish, or an entry
          that isn't this company's own currency in the second case):
          not applicable, returns ``None``.
        """
        if company_currency == VEF_CURRENCY_CODE:
            return moneda
        if (
            company_currency in BCV_PUBLISHED_CURRENCIES
            and moneda == company_currency
        ):
            return VEF_CURRENCY_CODE
        return None

    def _bcv_sync_is_valid_rate_date(self, current_date, published_date):
        """Decides whether ``published_date`` should be applied as
        today's rate for this company. Fully self-contained to this
        module -- it does not call ``l10n_ve_currency_rate_live``'s own
        ``_is_valid_rate_date`` (that method's past-date branch exists
        for a different caller, that module's own scraping/fallback
        flow). The only thing reused from that module is the
        ``can_update_habil_days`` field itself.

        - ``published_date`` is today: always valid -- BCV's own rate for
          today always applies, regardless of the flag.
        - ``published_date`` is in the future: valid only if
          ``can_update_habil_days`` is enabled. BCV publishes the next
          business day's rate in advance (e.g. Friday afternoon for
          Monday, or for Tuesday directly if Monday is a bank holiday).
          When the flag is disabled, an advance rate is rejected --
          nothing gets written, so the last stored rate simply stays in
          effect.
        - ``published_date`` is in the past: always invalid, regardless
          of the flag. BCV Sync's feed never legitimately carries a past
          date (BCV's own site always shows today's rate or an advance
          one, never a stale one), so this endpoint never backdates an
          existing rate record.
        """
        if published_date == current_date:
            return True
        if published_date > current_date:
            return bool(self.can_update_habil_days)
        return False

    @api.model
    def _bcv_sync_parse_valor(self, raw_value):
        """``tasas[].valor`` arrives as a string to avoid losing precision.
        Returns a strictly positive ``float``, or ``None`` if it can't be
        parsed (never raises)."""
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            return None
        return value if value > 0 else None

    @api.model
    def _bcv_sync_parse_fecha_valor(self, raw_date):
        """``tasas[].fecha_valor`` arrives as a ``YYYY-MM-DD`` string.
        Returns a ``date``, or ``None`` if it can't be parsed (never
        raises)."""
        if not raw_date:
            return None
        try:
            return fields.Date.to_date(raw_date)
        except ValueError:
            return None
